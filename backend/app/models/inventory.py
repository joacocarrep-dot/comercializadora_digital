"""
Inventory model for tracking product and variant stock levels.

Manages inventory quantities, reserved stock, and low stock alerts
for both products and variants.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.sql import func

from app.models.base import Base, UUIDMixin


class Inventory(Base, UUIDMixin):
    """
    Inventory entity representing stock levels.
    
    Attributes:
        product_id: Foreign key to product (nullable if variant_id present)
        variant_id: Foreign key to product variant (nullable if product_id present)
        quantity: Available stock quantity
        reserved_qty: Reserved stock quantity
        low_stock_alert: Threshold for low stock alerts
        warehouse_id: Optional foreign key to warehouse (future use)
        track_inventory: Whether to track inventory for this item
        allow_backorder: Whether to allow backorders
        updated_at: Last update timestamp
    """
    
    __tablename__ = "inventory"
    
    # Foreign keys (at least one must be non-null)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    reserved_qty: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    low_stock_alert: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    
    warehouse_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    
    track_inventory: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    allow_backorder: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "product_id IS NOT NULL OR variant_id IS NOT NULL",
            name="ck_inventory_product_or_variant"
        ),
        UniqueConstraint(
            "product_id", "variant_id", "warehouse_id",
            name="uq_inventory_product_variant_warehouse"
        ),
    )
    
    # Relationships
    product: Mapped[Optional["Product"]] = relationship(
        "Product",
        back_populates="inventory_records",
        lazy="select",
    )
    
    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant",
        back_populates="inventory_records",
        lazy="select",
    )
    
    @property
    def available_qty(self) -> int:
        """Calculate available quantity (quantity - reserved_qty)."""
        return self.quantity - self.reserved_qty
    
    @validates("quantity", "reserved_qty")
    def validate_inventory_fields(self, key: str, value: int) -> int:
        """Validate quantity and reserved_qty fields."""
        # Validación 1: Asegurar que ambos sean no negativos
        if value < 0:
            raise ValueError(f"{key} must be non-negative")
        
        # Validación 2: Asegurar que reserved_qty no exceda quantity
        if key == "reserved_qty":
            if value > self.quantity:
                raise ValueError("reserved_qty cannot exceed quantity")
        
        return value    
    def __repr__(self) -> str:
        return f"<Inventory(id={self.id}, product_id={self.product_id}, variant_id={self.variant_id}, qty={self.quantity}, reserved={self.reserved_qty})>"