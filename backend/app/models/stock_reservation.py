"""
StockReservation model for managing temporary stock reservations.

Handles temporary stock holds during the checkout process to prevent
overselling while allowing customers time to complete payment.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin, UUIDMixin


class StockReservationStatus(str, enum.Enum):
    """
    Stock reservation status enumeration.

    active: Stock is currently reserved
    released: Reservation expired or was manually released
    confirmed: Reservation confirmed (stock permanently allocated)
    """
    ACTIVE = "active"
    RELEASED = "released"
    CONFIRMED = "confirmed"


class StockReservation(Base, UUIDMixin, TimestampMixin):
    """
    Stock reservation entity for temporary stock holds.

    Attributes:
        order_id: Foreign key to order (required)
        inventory_id: Foreign key to inventory record (required)
        quantity: Quantity of stock reserved
        expires_at: Timestamp when reservation expires (15 minutes from creation)
        status: Current reservation status (active, released, confirmed)
        released_at: Timestamp when reservation was released (if applicable)
        confirmed_at: Timestamp when reservation was confirmed (if applicable)
        notes: Optional notes about the reservation
    """

    __tablename__ = "stock_reservations"

    # Foreign keys
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reservation details
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )

    status: Mapped[StockReservationStatus] = mapped_column(
        enum.Enum(StockReservationStatus, name="stock_reservation_status", native_enum=False),
        nullable=False,
        default=StockReservationStatus.ACTIVE,
        index=True,
    )

    released_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        nullable=True,
    )

    # Constraints
    __table_args__ = (
        # Ensure positive quantity
        CheckConstraint("quantity > 0", name="ck_stock_reservation_quantity_positive"),
        # Ensure expires_at is after created_at (valid reservation period)
        CheckConstraint("expires_at > created_at", name="ck_stock_reservation_expires_after_created"),
        # Status-specific timestamp validation
        CheckConstraint(
            "(status != 'released' OR released_at IS NOT NULL) AND "
            "(status = 'released' OR released_at IS NULL)",
            name="ck_stock_reservation_released_timestamp"
        ),
        CheckConstraint(
            "(status != 'confirmed' OR confirmed_at IS NOT NULL) AND "
            "(status = 'confirmed' OR confirmed_at IS NULL)",
            name="ck_stock_reservation_confirmed_timestamp"
        ),
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="stock_reservations",
        lazy="select",
    )

    inventory: Mapped["Inventory"] = relationship(
        "Inventory",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<StockReservation(id={self.id}, order_id={self.order_id}, inventory_id={self.inventory_id}, quantity={self.quantity}, status={self.status})>"