"""
Payment model for managing payment transactions.

Handles payment processing through various providers (MercadoPago, Stripe, etc.)
and tracks payment status, external payment IDs, and payment events.
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class PaymentStatus(str, enum.Enum):
    """
    Payment status enumeration representing payment lifecycle.

    Maps to provider-specific statuses (MercadoPago: pending, approved, rejected, refunded).
    """
    PENDING = "pending"           # Payment created, awaiting user action
    IN_PROCESS = "in_process"     # Payment in process (provider-specific)
    APPROVED = "approved"         # Payment successfully completed
    REJECTED = "rejected"         # Payment rejected/failed
    CANCELLED = "cancelled"       # Payment cancelled by user or system
    REFUNDED = "refunded"         # Payment refunded to customer
    CHARGED_BACK = "charged_back" # Payment charged back by customer


class PaymentProvider(str, enum.Enum):
    """
    Payment provider enumeration for supported payment gateways.
    """
    MERCADOPAGO = "mercadopago"
    STRIPE = "stripe"
    PAYPAL = "paypal"


class Payment(Base, UUIDMixin, TimestampMixin):
    """
    Payment entity representing a payment transaction for an order.

    Attributes:
        order_id: Foreign key to order (required)
        storefront_id: Foreign key to storefront (required)
        provider: Payment provider (mercadopago, stripe, etc.)
        external_payment_id: Provider's payment ID (e.g., MercadoPago payment ID)
        amount: Payment amount
        currency: Currency code (e.g., "ARS", "USD")
        status: Current payment status from PaymentStatus enum
        payment_method: Payment method used (credit_card, debit_card, wallet, etc.)
        card_last_four: Last four digits of credit/debit card (if applicable)
        init_point: Payment initialization URL for redirecting user to provider
        webhook_received_at: Timestamp when webhook notification was received
        metadata: JSONB flexible metadata for payment extensions
        notes: Optional notes about the payment
    """

    __tablename__ = "payments"

    # Foreign keys
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    storefront_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storefronts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Provider and external reference
    provider: Mapped[PaymentProvider] = mapped_column(
        Enum(PaymentProvider, name="payment_provider", native_enum=False),
        nullable=False,
        index=True,
    )

    external_payment_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Provider's payment ID (e.g., MercadoPago payment ID)",
    )

    # Monetary fields
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="ARS",
    )

    # Status
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", native_enum=False),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )

    # Payment method details
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Payment method used (credit_card, debit_card, wallet, etc.)",
    )

    card_last_four: Mapped[Optional[str]] = mapped_column(
        String(4),
        nullable=True,
        comment="Last four digits of credit/debit card",
    )

    # Payment URLs and timestamps
    init_point: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Payment initialization URL for redirecting user to provider",
    )

    webhook_received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when webhook notification was received",
    )

    # Additional fields
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Flexible metadata for payment extensions",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Constraints
    __table_args__ = (
        # Ensure amount is positive
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        # Ensure external_payment_id is unique per provider
        # Note: This may need to be (provider, external_payment_id) unique constraint
        # but external_payment_id can be null initially, so handled at application level
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="payments",
        lazy="select",
    )

    storefront: Mapped["Storefront"] = relationship(
        "Storefront",
        back_populates="payments",
        lazy="select",
    )

    payment_events: Mapped[list["PaymentEvent"]] = relationship(
        "PaymentEvent",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="PaymentEvent.created_at.asc()",
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, order_id={self.order_id}, status={self.status}, amount={self.amount})>"