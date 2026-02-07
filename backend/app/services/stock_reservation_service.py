"""
Stock reservation service for managing temporary stock holds.

Handles creation, release, and confirmation of stock reservations
during the checkout process to prevent overselling.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    ForbiddenException,
)
from app.models.stock_reservation import StockReservation, StockReservationStatus
from app.models.order import Order, OrderStatus
from app.models.inventory import Inventory
from app.repositories.base import BaseRepository


class StockReservationService:
    """
    Service for stock reservation business logic operations.

    Attributes:
        session: Async database session
        stock_reservation_repo: BaseRepository for StockReservation model
        order_repo: BaseRepository for Order model
        inventory_repo: BaseRepository for Inventory model
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize stock reservation service with database session.

        Args:
            session: Async database session
        """
        self.session = session
        self.stock_reservation_repo = BaseRepository(StockReservation, session)
        self.order_repo = BaseRepository(Order, session)
        self.inventory_repo = BaseRepository(Inventory, session)

    async def create_reservation(
        self,
        order_id: uuid.UUID,
        inventory_id: uuid.UUID,
        quantity: int,
        expires_in_minutes: int = 15,
        notes: Optional[str] = None,
    ) -> StockReservation:
        """
        Create a new stock reservation.

        Validates order and inventory existence, checks available stock,
        and creates a reservation with active status.

        Args:
            order_id: Order ID
            inventory_id: Inventory ID
            quantity: Quantity to reserve
            expires_in_minutes: Minutes until reservation expires (default: 15)
            notes: Optional notes about the reservation

        Returns:
            Created StockReservation instance

        Raises:
            NotFoundException: If order or inventory not found
            BadRequestException: If quantity is invalid or insufficient stock
        """
        if quantity <= 0:
            raise BadRequestException("Reservation quantity must be positive")

        # Validate order exists and is in a reservable state
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundException("Order", order_id)

        if order.status not in [OrderStatus.CREATED, OrderStatus.VALIDATING_STOCK, OrderStatus.RESERVED]:
            raise BadRequestException(
                f"Cannot create reservation for order with status {order.status}. "
                f"Order must be in 'created', 'validating_stock', or 'reserved' state."
            )

        # Validate inventory exists
        inventory = await self.inventory_repo.get_by_id(inventory_id)
        if not inventory:
            raise NotFoundException("Inventory", inventory_id)

        # Check available stock
        available_qty = inventory.available_qty
        if available_qty < quantity and inventory.track_inventory and not inventory.allow_backorder:
            raise BadRequestException(
                f"Insufficient stock available. Requested: {quantity}, Available: {available_qty}"
            )

        # Calculate expiration time
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

        # Create reservation
        reservation_data = {
            "order_id": order_id,
            "inventory_id": inventory_id,
            "quantity": quantity,
            "expires_at": expires_at,
            "status": StockReservationStatus.ACTIVE,
            "notes": notes,
        }

        reservation = await self.stock_reservation_repo.create(**reservation_data)

        # Update inventory reserved quantity
        new_reserved_qty = inventory.reserved_qty + quantity
        await self.inventory_repo.update(
            inventory.id,
            reserved_qty=new_reserved_qty,
        )

        return reservation

    async def release_reservation(
        self,
        reservation_id: uuid.UUID,
        reason: Optional[str] = None,
        released_by: Optional[uuid.UUID] = None,
    ) -> StockReservation:
        """
        Release a stock reservation.

        Updates reservation status to 'released', decrements inventory.reserved_qty,
        and sets released_at timestamp.

        Args:
            reservation_id: Stock reservation ID
            reason: Optional reason for release
            released_by: User ID who released the reservation

        Returns:
            Updated StockReservation instance

        Raises:
            NotFoundException: If reservation not found
            BadRequestException: If reservation is not active or already released/confirmed
        """
        reservation = await self.stock_reservation_repo.get_by_id(reservation_id)
        if not reservation:
            raise NotFoundException("StockReservation", reservation_id)

        if reservation.status != StockReservationStatus.ACTIVE:
            raise BadRequestException(
                f"Cannot release reservation with status {reservation.status}. "
                f"Only active reservations can be released."
            )

        # Get inventory record
        inventory = await self.inventory_repo.get_by_id(reservation.inventory_id)
        if inventory:
            # Decrement reserved quantity (ensure it doesn't go negative)
            new_reserved_qty = max(0, inventory.reserved_qty - reservation.quantity)
            await self.inventory_repo.update(
                inventory.id,
                reserved_qty=new_reserved_qty,
            )

        # Update reservation
        notes = reservation.notes or ""
        if reason:
            notes = f"{notes}\nReleased: {reason}".strip()

        updated_reservation = await self.stock_reservation_repo.update(
            reservation_id,
            status=StockReservationStatus.RELEASED,
            released_at=datetime.utcnow(),
            released_by=released_by,
            notes=notes,
        )

        return updated_reservation

    async def confirm_reservation(
        self,
        reservation_id: uuid.UUID,
        confirmed_by: Optional[uuid.UUID] = None,
    ) -> StockReservation:
        """
        Confirm a stock reservation.

        Updates reservation status to 'confirmed', updates inventory quantities
        (decrements actual quantity, clears reserved quantity), and sets confirmed_at timestamp.

        Args:
            reservation_id: Stock reservation ID
            confirmed_by: User ID who confirmed the reservation

        Returns:
            Updated StockReservation instance

        Raises:
            NotFoundException: If reservation not found
            BadRequestException: If reservation is not active
        """
        reservation = await self.stock_reservation_repo.get_by_id(reservation_id)
        if not reservation:
            raise NotFoundException("StockReservation", reservation_id)

        if reservation.status != StockReservationStatus.ACTIVE:
            raise BadRequestException(
                f"Cannot confirm reservation with status {reservation.status}. "
                f"Only active reservations can be confirmed."
            )

        # Get inventory record
        inventory = await self.inventory_repo.get_by_id(reservation.inventory_id)
        if not inventory:
            raise NotFoundException("Inventory", reservation.inventory_id)

        # Update inventory quantities
        # Decrement actual quantity (since stock is now permanently allocated)
        # Clear reserved quantity (since it's being converted to actual sale)
        new_quantity = max(0, inventory.quantity - reservation.quantity)
        new_reserved_qty = max(0, inventory.reserved_qty - reservation.quantity)

        await self.inventory_repo.update(
            inventory.id,
            quantity=new_quantity,
            reserved_qty=new_reserved_qty,
        )

        # Update reservation
        updated_reservation = await self.stock_reservation_repo.update(
            reservation_id,
            status=StockReservationStatus.CONFIRMED,
            confirmed_at=datetime.utcnow(),
            confirmed_by=confirmed_by,
        )

        return updated_reservation

    async def get_active_reservations_for_order(
        self,
        order_id: uuid.UUID,
    ) -> list[StockReservation]:
        """
        Get all active reservations for a specific order.

        Args:
            order_id: Order ID

        Returns:
            List of active StockReservation instances
        """
        query = select(StockReservation).where(
            and_(
                StockReservation.order_id == order_id,
                StockReservation.status == StockReservationStatus.ACTIVE,
            )
        ).order_by(StockReservation.expires_at.asc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_expired_reservations(
        self,
        limit: int = 100,
    ) -> list[StockReservation]:
        """
        Get expired but still active reservations.

        Useful for cleanup jobs that release expired reservations.

        Args:
            limit: Maximum number of reservations to return

        Returns:
            List of expired active StockReservation instances
        """
        query = select(StockReservation).where(
            and_(
                StockReservation.status == StockReservationStatus.ACTIVE,
                StockReservation.expires_at <= datetime.utcnow(),
            )
        ).order_by(StockReservation.expires_at.asc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def bulk_release_expired_reservations(
        self,
        limit: int = 100,
        released_by: Optional[uuid.UUID] = None,
    ) -> dict:
        """
        Release multiple expired reservations in bulk.

        Used by periodic cleanup jobs to automatically release stock
        when reservations expire without payment.

        Args:
            limit: Maximum number of reservations to process
            released_by: User ID who released the reservations (system job)

        Returns:
            Dictionary with processing results
        """
        expired_reservations = await self.get_expired_reservations(limit=limit)
        released_count = 0
        failed_reservations = []

        for reservation in expired_reservations:
            try:
                await self.release_reservation(
                    reservation_id=reservation.id,
                    reason="reservation_expired",
                    released_by=released_by,
                )
                released_count += 1
            except Exception as e:
                failed_reservations.append({
                    "reservation_id": str(reservation.id),
                    "error": str(e),
                })

        return {
            "total_processed": len(expired_reservations),
            "released_count": released_count,
            "failed_count": len(failed_reservations),
            "failed_reservations": failed_reservations,
        }