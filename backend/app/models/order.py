"""
Order model for managing customer orders.

Handles the complete order lifecycle from creation to completion,
including stock reservations, pricing calculations, and status tracking.
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class OrderStatus(str, enum.Enum):
    """
    Order status enumeration representing the order lifecycle.

    Flow: created → validating_stock → reserved → payment_pending → paid → processing → completed
    Cancellation can happen at any point before completion.
    """
    CREATED = "created"                     # Order created from cart, awaiting validation
    VALIDATING_STOCK = "validating_stock"   # Validating stock availability
    RESERVED = "reserved"                   # Stock reserved, awaiting payment
    PAYMENT_PENDING = "payment_pending"     # Payment initiated, awaiting confirmation
    PAID = "paid"                           # Payment confirmed, order being processed
    PROCESSING = "processing"               # Order being prepared for shipment
    COMPLETED = "completed"                 # Order delivered/completed
    CANCELLED = "cancelled"                 # Order cancelled


class Order(Base, UUIDMixin, TimestampMixin):
    """
    Order entity representing a customer purchase.

    Attributes:
        order_number: Unique order identifier for customer reference (e.g., "ORD-20250207-ABC123")
        storefront_id: Foreign key to storefront (required)
        user_id: Foreign key to user (nullable for guest checkout)
        status: Current order status from OrderStatus enum
        subtotal: Sum of all order items before shipping and tax
        shipping_amount: Shipping cost
        tax_amount: Tax amount
        total_amount: Final total (subtotal + shipping + tax)
        currency: Currency code (e.g., "ARS", "USD")
        shipping_address: JSONB shipping address details
        billing_address: JSONB billing address details
        reserved_at: Timestamp when stock was reserved
        reservation_expires_at: Timestamp when reservation expires (15 minutes)
        notes: Optional notes from customer or staff
        metadata: JSONB flexible metadata for order extensions
    """

    __tablename__ = "orders"

    # Unique order identifier for customer reference
    order_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    # Foreign keys
    storefront_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storefronts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Status
    status: Mapped[OrderStatus] = mapped_column(
        enum.Enum(OrderStatus, name="order_status", native_enum=False),
        nullable=False,
        default=OrderStatus.CREATED,
        index=True,
    )

    # Monetary fields
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    shipping_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="ARS",
    )

    # Address fields (JSONB for flexibility)
    shipping_address: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    billing_address: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Reservation timestamps
    reserved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reservation_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Metadata for extensions
    order_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )

    # Constraints
    __table_args__ = (
        # Ensure monetary amounts are non-negative
        CheckConstraint("subtotal >= 0", name="ck_order_subtotal_non_negative"),
        CheckConstraint("shipping_amount >= 0", name="ck_order_shipping_non_negative"),
        CheckConstraint("tax_amount >= 0", name="ck_order_tax_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_order_total_non_negative"),
        # Ensure total equals subtotal + shipping + tax (within reasonable rounding)
        CheckConstraint(
            "ABS(total_amount - (subtotal + shipping_amount + tax_amount)) < 0.01",
            name="ck_order_total_calculation"
        ),
        # Guest orders must have at least user_id or contact info in metadata
        # Note: This will be validated at application level
    )

    # Relationships
    storefront: Mapped["Storefront"] = relationship(
        "Storefront",
        back_populates="orders",
        lazy="select",
    )

    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="orders",
        lazy="select",
    )

    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
    )

    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="OrderStatusHistory.created_at.desc()",
    )

    stock_reservations: Mapped[list["StockReservation"]] = relationship(
        "StockReservation",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, order_number={self.order_number}, status={self.status}, total={self.total_amount})>"