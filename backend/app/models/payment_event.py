"""
PaymentEvent model for tracking payment-related events and webhook notifications.

Records events such as payment creation, status updates, webhook notifications,
and provider-specific events for audit trail and idempotency handling.
"""
import enum
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Enum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.payment import PaymentStatus


class PaymentEventType(str, enum.Enum):
    """
    Payment event type enumeration for categorizing payment events.
    """
    PAYMENT_CREATED = "payment_created"           # Payment record created
    PAYMENT_INITIATED = "payment_initiated"       # Payment initiated with provider
    PAYMENT_PENDING = "payment_pending"           # Payment pending user action
    PAYMENT_IN_PROCESS = "payment_in_process"     # Payment in process
    PAYMENT_APPROVED = "payment_approved"         # Payment approved/completed
    PAYMENT_REJECTED = "payment_rejected"         # Payment rejected/failed
    PAYMENT_CANCELLED = "payment_cancelled"       # Payment cancelled
    PAYMENT_REFUNDED = "payment_refunded"         # Payment refunded
    PAYMENT_CHARGED_BACK = "payment_charged_back" # Payment charged back
    WEBHOOK_RECEIVED = "webhook_received"         # Webhook notification received
    WEBHOOK_PROCESSED = "webhook_processed"       # Webhook notification processed
    PROVIDER_EVENT = "provider_event"             # Provider-specific event
    ERROR = "error"                               # Error occurred during payment processing


class PaymentEvent(Base, UUIDMixin, TimestampMixin):
    """
    Payment event entity for tracking payment lifecycle events.

    Attributes:
        payment_id: Foreign key to payment (required)
        event_type: Type of payment event from PaymentEventType enum
        event_data: JSONB data containing event details (provider response, webhook payload, etc.)
        provider_event_id: Provider's event ID for deduplication (optional)
        status_before: Payment status before this event (optional)
        status_after: Payment status after this event (optional)
        error_message: Error message if event_type is 'error' (optional)
        processed_by: Identifier of who processed the event (system, webhook, admin, etc.)
    """

    __tablename__ = "payment_events"

    # Foreign key
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event details
    event_type: Mapped[PaymentEventType] = mapped_column(
        Enum(PaymentEventType, name="payment_event_type", native_enum=False),
        nullable=False,
        index=True,
    )

    event_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON data containing event details (provider response, webhook payload, etc.)",
    )

    provider_event_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Provider's event ID for deduplication",
    )

    # Status tracking
    status_before: Mapped[Optional[PaymentStatus]] = mapped_column(
        Enum(PaymentStatus, name="payment_status", native_enum=False),
        nullable=True,
    )

    status_after: Mapped[Optional[PaymentStatus]] = mapped_column(
        Enum(PaymentStatus, name="payment_status", native_enum=False),
        nullable=True,
    )

    # Error details
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    processed_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Identifier of who processed the event (system, webhook, admin, etc.)",
    )

    # Relationships
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="payment_events",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<PaymentEvent(id={self.id}, payment_id={self.payment_id}, event_type={self.event_type})>"