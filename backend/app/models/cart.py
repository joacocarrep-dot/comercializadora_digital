"""
Cart model for managing shopping carts.

Supports both authenticated users and anonymous shoppers with automatic
cart merging upon login. Carts do not reserve stock or expire, only
store items with prices at the time of addition.
"""
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Cart(Base, UUIDMixin, TimestampMixin):
    """
    Cart entity representing a shopping cart.

    Attributes:
        storefront_id: Foreign key to storefront (required)
        user_id: Foreign key to user (nullable, anonymous carts have NULL)
        anonymous_id: Anonymous identifier for unauthenticated users (nullable)
        contact_email: Contact email for guest checkout
        contact_phone: Contact phone for guest checkout
        metadata: JSONB flexible metadata for cart extensions
    """

    __tablename__ = "carts"

    # Foreign keys
    storefront_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storefronts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    anonymous_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    contact_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    cart_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )

    # Constraints
    __table_args__ = (
        # At least one of user_id or anonymous_id must be provided
        CheckConstraint(
            "user_id IS NOT NULL OR anonymous_id IS NOT NULL",
            name="ck_cart_user_or_anonymous"
        ),
        # Composite index for efficient anonymous cart lookup
        UniqueConstraint(
            "storefront_id", "anonymous_id",
            name="uq_cart_storefront_anonymous",
        ),
        # Composite index for efficient user cart lookup (user_id already indexed individually)
        # Storefront + contact_email index for guest checkout lookups
    )

    # Relationships
    storefront: Mapped["Storefront"] = relationship(
        "Storefront",
        back_populates="carts",
        lazy="select",
    )

    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="carts",
        lazy="select",
    )

    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Cart(id={self.id}, storefront_id={self.storefront_id}, user_id={self.user_id}, anonymous_id={self.anonymous_id})>"