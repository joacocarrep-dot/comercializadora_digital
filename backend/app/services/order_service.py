"""
Order service for managing customer orders.

Handles order CRUD operations, status updates, order retrieval,
and order cancellation with proper business logic validations.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    ForbiddenException,
)
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.stock_reservation import StockReservation, StockReservationStatus
from app.models.user import User
from app.models.storefront import Storefront
from app.repositories.base import BaseRepository


class OrderService:
    """
    Service for order business logic operations.

    Attributes:
        session: Async database session
        order_repo: BaseRepository for Order model
        order_item_repo: BaseRepository for OrderItem model
        status_history_repo: BaseRepository for OrderStatusHistory model
        stock_reservation_repo: BaseRepository for StockReservation model
        user_repo: BaseRepository for User model
        storefront_repo: BaseRepository for Storefront model
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize order service with database session.

        Args:
            session: Async database session
        """
        self.session = session
        self.order_repo = BaseRepository(Order, session)
        self.order_item_repo = BaseRepository(OrderItem, session)
        self.status_history_repo = BaseRepository(OrderStatusHistory, session)
        self.stock_reservation_repo = BaseRepository(StockReservation, session)
        self.user_repo = BaseRepository(User, session)
        self.storefront_repo = BaseRepository(Storefront, session)

    async def create_order(
        self,
        storefront_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        order_number: Optional[str] = None,
        subtotal: Decimal = Decimal("0.00"),
        shipping_amount: Decimal = Decimal("0.00"),
        tax_amount: Decimal = Decimal("0.00"),
        currency: str = "ARS",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Order:
        """
        Create a new order.

        Validates storefront and user existence, generates order number if not provided,
        and creates initial status history entry.

        Args:
            storefront_id: Storefront ID
            user_id: Optional user ID (for authenticated users)
            order_number: Optional custom order number (auto-generated if not provided)
            subtotal: Order subtotal
            shipping_amount: Shipping cost
            tax_amount: Tax amount
            currency: Currency code (default: "ARS")
            metadata: Optional order metadata

        Returns:
            Newly created Order instance

        Raises:
            NotFoundException: If storefront or user not found
            BadRequestException: If monetary values are invalid
        """
        # Validate storefront exists
        storefront = await self.storefront_repo.get_by_id(storefront_id)
        if not storefront:
            raise NotFoundException("Storefront", storefront_id)

        # Validate user exists if provided
        if user_id:
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise NotFoundException("User", user_id)

        # Validate monetary values
        if subtotal < 0:
            raise BadRequestException("Subtotal must be non-negative")
        if shipping_amount < 0:
            raise BadRequestException("Shipping amount must be non-negative")
        if tax_amount < 0:
            raise BadRequestException("Tax amount must be non-negative")

        # Calculate total
        total_amount = subtotal + shipping_amount + tax_amount

        # Generate order number if not provided
        if not order_number:
            order_number = await self._generate_order_number(storefront_id)

        # Check if order number already exists
        existing_order = await self._get_order_by_number(order_number)
        if existing_order:
            raise ConflictException(f"Order number '{order_number}' already exists")

        # Create order
        order_data = {
            "order_number": order_number,
            "storefront_id": storefront_id,
            "user_id": user_id,
            "status": OrderStatus.CREATED,
            "subtotal": subtotal,
            "shipping_amount": shipping_amount,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "currency": currency,
            "order_metadata": metadata or {},
        }

        order = await self.order_repo.create(**order_data)

        # Create initial status history entry
        await self.status_history_repo.create(
            order_id=order.id,
            from_status=None,
            to_status=OrderStatus.CREATED,
            reason="order_created",
            notes="Order created",
            changed_by=user_id,
        )

        return order

    async def update_status(
        self,
        order_id: uuid.UUID,
        new_status: OrderStatus,
        reason: str,
        notes: Optional[str] = None,
        changed_by: Optional[uuid.UUID] = None,
    ) -> Order:
        """
        Update order status with validation.

        Validates status transitions, creates status history entry,
        and handles special cases like cancellation.

        Args:
            order_id: Order ID
            new_status: New order status
            reason: Reason for status change
            notes: Additional notes
            changed_by: User ID who changed the status

        Returns:
            Updated Order instance

        Raises:
            NotFoundException: If order not found
            BadRequestException: If status transition is invalid
        """
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order", order_id)

        # Validate status transition
        if not self._is_valid_status_transition(order.status, new_status):
            raise BadRequestException(
                f"Cannot transition order from {order.status} to {new_status}"
            )

        # Handle cancellation
        if new_status == OrderStatus.CANCELLED:
            order = await self._handle_order_cancellation(order_id, changed_by)

        # Update order status
        updated_order = await self.order_repo.update(
            order_id,
            status=new_status,
        )

        # Create status history entry
        await self.status_history_repo.create(
            order_id=order_id,
            from_status=order.status,
            to_status=new_status,
            reason=reason,
            notes=notes or f"Status changed from {order.status} to {new_status}",
            changed_by=changed_by,
        )

        return updated_order

    async def get_by_user(
        self,
        user_id: uuid.UUID,
        storefront_id: Optional[uuid.UUID] = None,
        status: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 50,
        include_items: bool = False,
    ) -> List[Order]:
        """
        Get orders for a specific user with optional filtering.

        Args:
            user_id: User ID
            storefront_id: Optional storefront filter
            status: Optional status filter
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
            include_items: Whether to include order items

        Returns:
            List of Order instances

        Raises:
            NotFoundException: If user not found
        """
        # Validate user exists
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        # Build query
        query = select(Order).where(Order.user_id == user_id)

        if storefront_id:
            query = query.where(Order.storefront_id == storefront_id)

        if status:
            query = query.where(Order.status == status)

        # Order by creation date (newest first)
        query = query.order_by(desc(Order.created_at))

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Execute query
        result = await self.session.execute(query)
        orders = list(result.scalars().all())

        # Load order items if requested
        if include_items and orders:
            order_ids = [order.id for order in orders]
            items_query = select(OrderItem).where(OrderItem.order_id.in_(order_ids))
            items_result = await self.session.execute(items_query)
            items_by_order = {}

            for item in items_result.scalars().all():
                if item.order_id not in items_by_order:
                    items_by_order[item.order_id] = []
                items_by_order[item.order_id].append(item)

            for order in orders:
                order.order_items = items_by_order.get(order.id, [])

        return orders

    async def get_by_number(
        self,
        order_number: str,
        include_items: bool = False,
        include_history: bool = False,
        include_reservations: bool = False,
    ) -> Optional[Order]:
        """
        Get order by order number.

        Args:
            order_number: Order number
            include_items: Whether to include order items
            include_history: Whether to include status history
            include_reservations: Whether to include stock reservations

        Returns:
            Order instance or None if not found
        """
        order = await self._get_order_by_number(order_number)
        if not order:
            return None

        # Load related data if requested
        if include_items:
            query = select(OrderItem).where(OrderItem.order_id == order.id)
            result = await self.session.execute(query)
            order.order_items = list(result.scalars().all())

        if include_history:
            query = select(OrderStatusHistory).where(
                OrderStatusHistory.order_id == order.id
            ).order_by(OrderStatusHistory.created_at.desc())
            result = await self.session.execute(query)
            order.status_history = list(result.scalars().all())

        if include_reservations:
            query = select(StockReservation).where(
                StockReservation.order_id == order.id
            )
            result = await self.session.execute(query)
            order.stock_reservations = list(result.scalars().all())

        return order

    async def cancel_order(
        self,
        order_id: uuid.UUID,
        reason: str,
        notes: Optional[str] = None,
        changed_by: Optional[uuid.UUID] = None,
    ) -> Order:
        """
        Cancel an order.

        Releases any stock reservations, updates order status to 'cancelled',
        and creates appropriate status history entries.

        Args:
            order_id: Order ID
            reason: Reason for cancellation
            notes: Additional notes
            changed_by: User ID who cancelled the order

        Returns:
            Updated Order instance

        Raises:
            NotFoundException: If order not found
            BadRequestException: If order cannot be cancelled
        """
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order", order_id)

        # Check if order can be cancelled
        if order.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
            raise BadRequestException(
                f"Cannot cancel order with status {order.status}"
            )

        # Update status to cancelled via update_status method
        # This will handle stock reservation release and status history
        cancelled_order = await self.update_status(
            order_id=order_id,
            new_status=OrderStatus.CANCELLED,
            reason=reason,
            notes=notes,
            changed_by=changed_by,
        )

        return cancelled_order

    async def _generate_order_number(self, storefront_id: uuid.UUID) -> str:
        """
        Generate unique order number.

        Args:
            storefront_id: Storefront ID

        Returns:
            Unique order number string
        """
        # Get storefront code
        storefront = await self.storefront_repo.get_by_id(storefront_id)
        if not storefront:
            raise NotFoundException("Storefront", storefront_id)

        storefront_code = storefront.code or str(storefront_id)[:8].upper()

        # Get sequence number
        query = select(Order).where(Order.storefront_id == storefront_id)
        result = await self.session.execute(query)
        existing_orders = list(result.scalars().all())
        sequence = len(existing_orders) + 1

        # Format: SF-{code}-{YYYYMMDD}-{sequence}
        date_str = datetime.utcnow().strftime("%Y%m%d")
        return f"SF-{storefront_code}-{date_str}-{sequence:06d}"

    async def _get_order_by_number(self, order_number: str) -> Optional[Order]:
        """Get order by order number."""
        query = select(Order).where(Order.order_number == order_number)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    def _is_valid_status_transition(self, current_status: OrderStatus, new_status: OrderStatus) -> bool:
        """
        Validate status transition.

        Args:
            current_status: Current order status
            new_status: Proposed new status

        Returns:
            True if transition is valid, False otherwise
        """
        # Define valid transitions
        valid_transitions = {
            OrderStatus.CREATED: [
                OrderStatus.VALIDATING_STOCK,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.VALIDATING_STOCK: [
                OrderStatus.RESERVED,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.RESERVED: [
                OrderStatus.PAYMENT_PENDING,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.PAYMENT_PENDING: [
                OrderStatus.PAID,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.PAID: [
                OrderStatus.PROCESSING,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.PROCESSING: [
                OrderStatus.COMPLETED,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.COMPLETED: [
                # Once completed, no further transitions
            ],
            OrderStatus.CANCELLED: [
                # Once cancelled, no further transitions
            ],
        }

        return new_status in valid_transitions.get(current_status, [])

    async def _handle_order_cancellation(
        self,
        order_id: uuid.UUID,
        changed_by: Optional[uuid.UUID] = None,
    ) -> Order:
        """
        Handle order cancellation logic.

        Releases stock reservations and updates inventory.

        Args:
            order_id: Order ID
            changed_by: User ID who cancelled the order

        Returns:
            Updated Order instance
        """
        # Get active stock reservations for this order
        query = select(StockReservation).where(
            and_(
                StockReservation.order_id == order_id,
                StockReservation.status == StockReservationStatus.ACTIVE,
            )
        )
        result = await self.session.execute(query)
        active_reservations = list(result.scalars().all())

        # Release each reservation
        for reservation in active_reservations:
            await self._release_stock_reservation(reservation.id, changed_by)

        return await self.order_repo.get_by_id(order_id)

    async def _release_stock_reservation(
        self,
        reservation_id: uuid.UUID,
        changed_by: Optional[uuid.UUID] = None,
    ) -> None:
        """
        Release a stock reservation.

        Updates reservation status to 'released' and decrements inventory.reserved_qty.

        Args:
            reservation_id: Stock reservation ID
            changed_by: User ID who released the reservation
        """
        reservation = await self.stock_reservation_repo.get_by_id(reservation_id)
        if not reservation:
            return

        # Get inventory record
        from app.models.inventory import Inventory
        inventory_repo = BaseRepository(Inventory, self.session)
        inventory = await inventory_repo.get_by_id(reservation.inventory_id)

        if inventory:
            # Decrement reserved quantity
            new_reserved_qty = max(0, inventory.reserved_qty - reservation.quantity)
            await inventory_repo.update(
                inventory.id,
                reserved_qty=new_reserved_qty,
            )

        # Update reservation status
        await self.stock_reservation_repo.update(
            reservation_id,
            status=StockReservationStatus.RELEASED,
            released_at=datetime.utcnow(),
            released_by=changed_by,
        )