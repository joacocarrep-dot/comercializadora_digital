"""
Checkout service for orchestrating the complete checkout flow.

Handles order creation from cart, stock validation, price validation,
stock reservations, shipping address management, and shipping calculation.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, select
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
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.storefront import Storefront
from app.models.inventory import Inventory
from app.repositories.base import BaseRepository
from app.services.cart_service import CartService
from app.services.product_service import ProductService
from app.services.inventory_service import InventoryService


class CheckoutService:
    """
    Service for checkout business logic operations.

    Attributes:
        session: Async database session
        order_repo: BaseRepository for Order model
        order_item_repo: BaseRepository for OrderItem model
        status_history_repo: BaseRepository for OrderStatusHistory model
        stock_reservation_repo: BaseRepository for StockReservation model
        cart_repo: BaseRepository for Cart model
        cart_item_repo: BaseRepository for CartItem model
        product_repo: BaseRepository for Product model
        product_variant_repo: BaseRepository for ProductVariant model
        storefront_repo: BaseRepository for Storefront model
        inventory_repo: BaseRepository for Inventory model
        cart_service: CartService instance
        product_service: ProductService instance
        inventory_service: InventoryService instance
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize checkout service with database session.

        Args:
            session: Async database session
        """
        self.session = session
        self.order_repo = BaseRepository(Order, session)
        self.order_item_repo = BaseRepository(OrderItem, session)
        self.status_history_repo = BaseRepository(OrderStatusHistory, session)
        self.stock_reservation_repo = BaseRepository(StockReservation, session)
        self.cart_repo = BaseRepository(Cart, session)
        self.cart_item_repo = BaseRepository(CartItem, session)
        self.product_repo = BaseRepository(Product, session)
        self.product_variant_repo = BaseRepository(ProductVariant, session)
        self.storefront_repo = BaseRepository(Storefront, session)
        self.inventory_repo = BaseRepository(Inventory, session)
        
        # Initialize other services
        self.cart_service = CartService(session)
        self.product_service = ProductService(session)
        self.inventory_service = InventoryService(session)

    async def init_checkout(
        self,
        cart_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Order:
        """
        Initialize checkout by creating an order from cart.

        Creates order with status 'created', copies cart items to order items,
        and calculates initial subtotal. Returns order with expires_at timestamp.

        Args:
            cart_id: ID of the cart to checkout
            user_id: Optional user ID for authenticated checkout

        Returns:
            Newly created Order instance

        Raises:
            NotFoundException: If cart not found or empty
            BadRequestException: If cart validation fails
        """
        # Get cart with items
        cart = await self._get_cart_with_items(cart_id)
        if not cart:
            raise NotFoundException("Cart", cart_id)

        if not cart.cart_items:
            raise BadRequestException("Cannot checkout empty cart")

        # Validate cart ownership
        if user_id and cart.user_id and cart.user_id != user_id:
            raise ForbiddenException("Cart does not belong to current user")

        # Generate order number
        order_number = await self._generate_order_number(cart.storefront_id)

        # Calculate subtotal from current prices (not price_at_addition)
        subtotal = Decimal("0.00")
        order_items_data = []

        for cart_item in cart.cart_items:
            # Get current price
            current_price = await self.cart_service._get_current_product_price(
                cart_item.product_id,
                cart_item.variant_id,
                cart.storefront_id,
            )

            item_total = current_price * Decimal(cart_item.quantity)
            subtotal += item_total

            # Prepare order item data with product snapshot
            product = await self.product_repo.get_by_id(cart_item.product_id)
            if not product:
                raise NotFoundException("Product", cart_item.product_id)

            variant = None
            if cart_item.variant_id:
                variant = await self.product_variant_repo.get_by_id(cart_item.variant_id)

            order_items_data.append({
                "product_id": cart_item.product_id,
                "variant_id": cart_item.variant_id,
                "product_name": product.name,
                "product_sku": variant.sku if variant else product.sku,
                "product_price": current_price,
                "quantity": cart_item.quantity,
                "unit_price": current_price,
                "total_price": item_total,
            })

        # Create order
        order_data = {
            "order_number": order_number,
            "storefront_id": cart.storefront_id,
            "user_id": cart.user_id or user_id,
            "status": OrderStatus.CREATED,
            "subtotal": subtotal,
            "shipping_amount": Decimal("0.00"),
            "tax_amount": Decimal("0.00"),
            "total_amount": subtotal,  # Will be updated with shipping/tax later
            "currency": "ARS",  # TODO: Make configurable per storefront
            "order_metadata": {
                "cart_id": str(cart_id),
                "created_from_cart": True,
            },
        }

        order = await self.order_repo.create(**order_data)

        # Create order items
        for item_data in order_items_data:
            await self.order_item_repo.create(
                order_id=order.id,
                **item_data
            )

        # Create initial status history entry
        await self.status_history_repo.create(
            order_id=order.id,
            from_status=None,
            to_status=OrderStatus.CREATED,
            reason="order_created",
            notes="Order created from cart",
            changed_by=user_id,
        )

        return order

    async def validate_stock(self, order_id: uuid.UUID) -> Dict[str, Any]:
        """
        Validate stock availability for all items in the order.

        Checks inventory.available_qty >= quantity for each item.
        Returns detailed information about items with insufficient stock.

        Args:
            order_id: ID of the order to validate

        Returns:
            Dictionary with validation results:
            {
                "is_valid": bool,
                "out_of_stock_items": List[Dict],
                "total_items": int,
                "available_items": int
            }

        Raises:
            NotFoundException: If order not found
            BadRequestException: If order status is not 'created' or 'validating_stock'
        """
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order", order_id)

        if order.status not in [OrderStatus.CREATED, OrderStatus.VALIDATING_STOCK]:
            raise BadRequestException(
                f"Cannot validate stock for order with status {order.status}. "
                f"Expected 'created' or 'validating_stock'."
            )

        # Update status to validating_stock if not already
        if order.status == OrderStatus.CREATED:
            await self._update_order_status(
                order_id,
                OrderStatus.VALIDATING_STOCK,
                "stock_validation_started",
                "Started stock validation",
                order.user_id,
            )

        # Get order items with product/variant info
        query = select(OrderItem).where(OrderItem.order_id == order_id)
        result = await self.session.execute(query)
        order_items = list(result.scalars().all())

        out_of_stock_items = []
        total_items = len(order_items)
        available_items = 0

        for order_item in order_items:
            # Get inventory record
            inventory = await self.inventory_service.get_inventory_by_product_variant(
                product_id=order_item.product_id,
                variant_id=order_item.variant_id,
            )

            if not inventory:
                # No inventory record - assume unlimited stock
                available_items += 1
                continue

            # Check availability
            if inventory.available_qty >= order_item.quantity:
                available_items += 1
            else:
                out_of_stock_items.append({
                    "order_item_id": str(order_item.id),
                    "product_id": str(order_item.product_id),
                    "variant_id": str(order_item.variant_id),
                    "product_name": order_item.product_name,
                    "product_sku": order_item.product_sku,
                    "quantity_requested": order_item.quantity,
                    "quantity_available": inventory.available_qty,
                    "allow_backorder": inventory.allow_backorder,
                })

        is_valid = len(out_of_stock_items) == 0

        return {
            "is_valid": is_valid,
            "out_of_stock_items": out_of_stock_items,
            "total_items": total_items,
            "available_items": available_items,
        }

    async def validate_prices(self, order_id: uuid.UUID) -> Dict[str, Any]:
        """
        Validate current prices vs prices saved in order items.

        Compares current product/variant prices with prices stored in order items.
        Returns items with price changes that require customer confirmation.

        Args:
            order_id: ID of the order to validate

        Returns:
            Dictionary with price validation results:
            {
                "requires_confirmation": bool,
                "price_changed_items": List[Dict],
                "total_price_difference": Decimal,
                "original_subtotal": Decimal,
                "current_subtotal": Decimal
            }

        Raises:
            NotFoundException: If order not found
        """
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order", order_id)

        # Get order items
        query = select(OrderItem).where(OrderItem.order_id == order_id)
        result = await self.session.execute(query)
        order_items = list(result.scalars().all())

        price_changed_items = []
        total_price_difference = Decimal("0.00")
        current_subtotal = Decimal("0.00")

        for order_item in order_items:
            # Get current price
            current_price = await self.cart_service._get_current_product_price(
                order_item.product_id,
                order_item.variant_id,
                order.storefront_id,
            )

            # Compare with stored price
            if current_price != order_item.unit_price:
                price_diff = current_price - order_item.unit_price
                item_total_diff = price_diff * Decimal(order_item.quantity)
                total_price_difference += item_total_diff

                price_changed_items.append({
                    "order_item_id": str(order_item.id),
                    "product_id": str(order_item.product_id),
                    "variant_id": str(order_item.variant_id),
                    "product_name": order_item.product_name,
                    "product_sku": order_item.product_sku,
                    "old_price": float(order_item.unit_price),
                    "new_price": float(current_price),
                    "quantity": order_item.quantity,
                    "price_difference": float(price_diff),
                    "total_price_difference": float(item_total_diff),
                })

            # Calculate current subtotal
            current_subtotal += current_price * Decimal(order_item.quantity)

        requires_confirmation = len(price_changed_items) > 0

        return {
            "requires_confirmation": requires_confirmation,
            "price_changed_items": price_changed_items,
            "total_price_difference": float(total_price_difference),
            "original_subtotal": float(order.subtotal),
            "current_subtotal": float(current_subtotal),
        }

    async def reserve_stock(self, order_id: uuid.UUID) -> Tuple[Order, List[StockReservation]]:
        """
        Reserve stock for order items for 15 minutes.

        Creates stock reservations, updates inventory.reserved_qty,
        and updates order status to 'reserved'.

        Args:
            order_id: ID of the order to reserve stock for

        Returns:
            Tuple of (updated Order, list of created StockReservation)

        Raises:
            NotFoundException: If order not found
            BadRequestException: If stock validation fails or order status invalid
        """
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order", order_id)

        if order.status != OrderStatus.VALIDATING_STOCK:
            raise BadRequestException(
                f"Cannot reserve stock for order with status {order.status}. "
                f"Expected 'validating_stock'."
            )

        # Validate stock first
        stock_validation = await self.validate_stock(order_id)
        if not stock_validation["is_valid"]:
            raise BadRequestException(
                "Cannot reserve stock: insufficient stock available",
                details={"out_of_stock_items": stock_validation["out_of_stock_items"]}
            )

        # Get order items
        query = select(OrderItem).where(OrderItem.order_id == order_id)
        result = await self.session.execute(query)
        order_items = list(result.scalars().all())

        # Calculate expiration (15 minutes from now)
        expires_at = datetime.utcnow() + timedelta(minutes=15)

        created_reservations = []

        for order_item in order_items:
            # Get inventory record
            inventory = await self.inventory_service.get_inventory_by_product_variant(
                product_id=order_item.product_id,
                variant_id=order_item.variant_id,
            )

            if not inventory:
                # Skip items without inventory tracking
                continue

            # Create stock reservation
            reservation_data = {
                "order_id": order_id,
                "inventory_id": inventory.id,
                "quantity": order_item.quantity,
                "expires_at": expires_at,
                "status": StockReservationStatus.ACTIVE,
            }

            reservation = await self.stock_reservation_repo.create(**reservation_data)
            created_reservations.append(reservation)

            # Update inventory reserved quantity
            new_reserved_qty = inventory.reserved_qty + order_item.quantity
            await self.inventory_repo.update(
                inventory.id,
                reserved_qty=new_reserved_qty,
            )

        # Update order status and reservation timestamps
        updated_order = await self.order_repo.update(
            order_id,
            status=OrderStatus.RESERVED,
            reserved_at=datetime.utcnow(),
            reservation_expires_at=expires_at,
        )

        # Create status history entry
        await self.status_history_repo.create(
            order_id=order_id,
            from_status=OrderStatus.VALIDATING_STOCK,
            to_status=OrderStatus.RESERVED,
            reason="stock_reserved",
            notes=f"Stock reserved for {len(created_reservations)} items, expires at {expires_at}",
            changed_by=order.user_id,
        )

        return updated_order, created_reservations

    async def add_shipping_address(
        self,
        order_id: uuid.UUID,
        shipping_address: Dict[str, Any],
        billing_address: Optional[Dict[str, Any]] = None,
    ) -> Order:
        """
        Add shipping and billing addresses to order.

        Validates required address fields and stores as JSONB.

        Args:
            order_id: ID of the order
            shipping_address: Shipping address details
            billing_address: Optional billing address details (uses shipping if not provided)

        Returns:
            Updated Order instance

        Raises:
            NotFoundException: If order not found
            BadRequestException: If address validation fails
        """
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order", order_id)

        # Validate required shipping address fields
        required_fields = ["first_name", "last_name", "address_line1", "city", "postal_code", "country"]
        for field in required_fields:
            if field not in shipping_address or not shipping_address[field]:
                raise BadRequestException(f"Shipping address field '{field}' is required")

        # Use shipping address for billing if not provided
        if billing_address is None:
            billing_address = shipping_address.copy()
        else:
            # Validate billing address fields
            for field in required_fields:
                if field not in billing_address or not billing_address[field]:
                    raise BadRequestException(f"Billing address field '{field}' is required")

        # Update order
        updated_order = await self.order_repo.update(
            order_id,
            shipping_address=shipping_address,
            billing_address=billing_address,
        )

        return updated_order

    async def calculate_shipping(
        self,
        order_id: uuid.UUID,
        shipping_method: str,
        shipping_options: Optional[Dict[str, Any]] = None,
    ) -> Order:
        """
        Calculate shipping cost and update order.

        This is a placeholder implementation that returns a fixed shipping cost.
        In a real implementation, this would integrate with shipping carriers.

        Args:
            order_id: ID of the order
            shipping_method: Shipping method identifier
            shipping_options: Optional shipping options

        Returns:
            Updated Order instance with shipping amount

        Raises:
            NotFoundException: If order not found
            BadRequestException: If shipping calculation fails
        """
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order", order_id)

        # Placeholder shipping calculation logic
        # In a real implementation, this would:
        # 1. Get order items with dimensions/weight
        # 2. Calculate total weight/volume
        # 3. Query shipping carrier API
        # 4. Return actual shipping cost

        shipping_amount = Decimal("10.00")  # Fixed placeholder

        # Recalculate total
        total_amount = order.subtotal + shipping_amount + order.tax_amount

        # Update order
        updated_order = await self.order_repo.update(
            order_id,
            shipping_amount=shipping_amount,
            total_amount=total_amount,
            order_metadata={
                **(order.order_metadata or {}),
                "shipping_method": shipping_method,
                "shipping_options": shipping_options or {},
                "shipping_calculated_at": datetime.utcnow().isoformat(),
            }
        )

        return updated_order

    async def _get_cart_with_items(self, cart_id: uuid.UUID) -> Optional[Cart]:
        """Get cart with items preloaded."""
        query = select(Cart).where(Cart.id == cart_id).options(
            select(Cart.cart_items)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _generate_order_number(self, storefront_id: uuid.UUID) -> str:
        """
        Generate unique order number in format: SF-{storefront_code}-{sequence}.

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

        # Get sequence number (count of existing orders for this storefront)
        query = select(Order).where(Order.storefront_id == storefront_id)
        result = await self.session.execute(query)
        existing_orders = list(result.scalars().all())
        sequence = len(existing_orders) + 1

        # Format: SF-{code}-{YYYYMMDD}-{sequence}
        date_str = datetime.utcnow().strftime("%Y%m%d")
        return f"SF-{storefront_code}-{date_str}-{sequence:06d}"

    async def _update_order_status(
        self,
        order_id: uuid.UUID,
        new_status: OrderStatus,
        reason: str,
        notes: str,
        changed_by: Optional[uuid.UUID] = None,
    ) -> Order:
        """
        Update order status and create history entry.

        Args:
            order_id: Order ID
            new_status: New status
            reason: Reason for status change
            notes: Additional notes
            changed_by: User ID who changed the status

        Returns:
            Updated Order instance
        """
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order", order_id)

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
            notes=notes,
            changed_by=changed_by,
        )

        return updated_order