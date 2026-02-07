"""
ProductVariant model for managing product variations.

Supports different variations of a product (e.g., color, size) with
custom options and price adjustments.
"""
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ProductVariant(Base, UUIDMixin, TimestampMixin):
    """
    ProductVariant entity representing a product variation.
    
    Attributes:
        product_id: Foreign key to parent product
        sku: Unique stock keeping unit for variant
        name: Variant display name
        price_adjustment: Price adjustment relative to base price
        options: JSONB flexible variant options
        image_url: Optional variant-specific image URL
        is_active: Whether variant is active
        position: Position for ordering variants
    """
    
    __tablename__ = "product_variants"
    
    # Foreign key
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    sku: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    price_adjustment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
        nullable=False,
    )
    
    options: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    position: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        index=True,
    )
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("product_id", "sku", name="uq_product_variant_sku"),
    )
    
    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="variants",
        lazy="select",
    )
    
    inventory_records: Mapped[list["Inventory"]] = relationship(
        "Inventory",
        back_populates="variant",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    bundle_items: Mapped[list["BundleItem"]] = relationship(
        "BundleItem",
        back_populates="variant",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="variant",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<ProductVariant(id={self.id}, sku={self.sku}, name={self.name}, product_id={self.product_id})>"
