"""
OrderStatusHistory model for tracking order status changes.

Records every status transition in an order's lifecycle with timestamps,
reasons, and user information for audit trail and analytics.
"""
import enum
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.order import OrderStatus


class OrderStatusHistory(Base, UUIDMixin, TimestampMixin):
    """
    Order status history entity for tracking status transitions.

    Attributes:
        order_id: Foreign key to order (required)
        from_status: Previous order status (nullable for initial status)
        to_status: New order status (required)
        reason: Reason for status change (e.g., 'customer_request', 'payment_received', 'stock_unavailable')
        notes: Optional detailed notes about the status change
        changed_by: Identifier of who changed the status (user_id, system, admin, etc.)
        changed_by_type: Type of entity that made the change (user, system, admin)
    """

    __tablename__ = "order_status_history"

    # Foreign key
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Status fields
    from_status: Mapped[Optional[OrderStatus]] = mapped_column(
        enum.Enum(OrderStatus, name="order_status", native_enum=False),
        nullable=True,
    )

    to_status: Mapped[OrderStatus] = mapped_column(
        enum.Enum(OrderStatus, name="order_status", native_enum=False),
        nullable=False,
        index=True,
    )

    # Change details
    reason: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    changed_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    changed_by_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="status_history",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<OrderStatusHistory(id={self.id}, order_id={self.order_id}, from={self.from_status}, to={self.to_status}, reason={self.reason})>"