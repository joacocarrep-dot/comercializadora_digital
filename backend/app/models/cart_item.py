"""
CartItem model for managing items in a shopping cart.

Each item represents a product or variant added to a cart with the
price at the time of addition for later comparison.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, UUIDMixin


class CartItem(Base, UUIDMixin):
    """
    CartItem entity representing an item in a shopping cart.

    Attributes:
        cart_id: Foreign key to cart (cascade delete)
        product_id: Foreign key to product
        variant_id: Foreign key to product variant (nullable)
        quantity: Quantity of the item in cart
        price_at_addition: Price of the item at the time it was added
        added_at: Timestamp when the item was added to cart
    """

    __tablename__ = "cart_items"

    # Foreign keys
    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    price_at_addition: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    added_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        nullable=False,
    )

    # Constraints
    __table_args__ = (
        # Each product/variant combination can only appear once per cart
        UniqueConstraint(
            "cart_id", "product_id", "variant_id",
            name="uq_cart_item_cart_product_variant"
        ),
        # Quantity must be positive
        CheckConstraint(
            "quantity > 0",
            name="ck_cart_item_positive_quantity"
        ),
    )

    # Relationships
    cart: Mapped["Cart"] = relationship(
        "Cart",
        back_populates="cart_items",
        lazy="select",
    )

    product: Mapped["Product"] = relationship(
        "Product",
        lazy="select",
    )

    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<CartItem(id={self.id}, cart_id={self.cart_id}, product_id={self.product_id}, variant_id={self.variant_id}, quantity={self.quantity})>"