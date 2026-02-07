"""
OrderItem model for items within a customer order.

Preserves product snapshot at the time of purchase including name,
SKU, price, and options to maintain historical accuracy even if
products change after the order is placed.
"""
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class OrderItem(Base, UUIDMixin):
    """
    Order item entity representing a purchased product/variant.

    Attributes:
        order_id: Foreign key to order (required)
        product_id: Foreign key to product (nullable if variant_id provided)
        variant_id: Foreign key to product variant (nullable if product_id provided)
        quantity: Quantity purchased
        unit_price: Price per unit at time of purchase
        total_price: Total price (unit_price * quantity)
        product_name: Snapshot of product name at purchase time
        product_sku: Snapshot of product SKU at purchase time
        variant_options: JSONB snapshot of variant options at purchase time
        notes: Optional notes about this specific item
    """

    __tablename__ = "order_items"

    # Foreign keys
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Quantity and pricing
    quantity: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    total_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # Product snapshot at time of purchase
    product_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    product_sku: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    variant_options: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Additional fields
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Constraints
    __table_args__ = (
        # At least one of product_id or variant_id must be provided
        CheckConstraint(
            "product_id IS NOT NULL OR variant_id IS NOT NULL",
            name="ck_order_item_product_or_variant"
        ),
        # Ensure positive quantity
        CheckConstraint("quantity > 0", name="ck_order_item_quantity_positive"),
        # Ensure non-negative prices
        CheckConstraint("unit_price >= 0", name="ck_order_item_unit_price_non_negative"),
        CheckConstraint("total_price >= 0", name="ck_order_item_total_price_non_negative"),
        # Ensure total_price equals unit_price * quantity (within rounding)
        CheckConstraint(
            "ABS(total_price - (unit_price * quantity)) < 0.01",
            name="ck_order_item_total_calculation"
        ),
        # Ensure product snapshot fields are not empty
        CheckConstraint("product_name != ''", name="ck_order_item_product_name_not_empty"),
        CheckConstraint("product_sku != ''", name="ck_order_item_product_sku_not_empty"),
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="order_items",
        lazy="select",
    )

    product: Mapped[Optional["Product"]] = relationship(
        "Product",
        back_populates="order_items",
        lazy="select",
    )

    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant",
        back_populates="order_items",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, order_id={self.order_id}, product_name={self.product_name}, quantity={self.quantity}, unit_price={self.unit_price})>"