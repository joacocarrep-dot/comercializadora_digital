"""
BundleItem model for managing product bundle compositions.

Represents the relationship between a bundle product and its component
products/variants, including quantities and positioning.
"""
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class BundleItem(Base, UUIDMixin, TimestampMixin):
    """
    BundleItem entity representing a component in a product bundle.
    
    Attributes:
        bundle_id: Foreign key to bundle product
        product_id: Foreign key to component product
        variant_id: Foreign key to component variant (nullable)
        quantity: Quantity of this component in the bundle
        position: Position for ordering components
    """
    
    __tablename__ = "bundle_items"
    
    # Foreign keys
    bundle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
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
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
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
        CheckConstraint(
            "bundle_id != product_id",
            name="ck_bundle_item_bundle_not_product"
        ),
        UniqueConstraint(
            "bundle_id", "product_id", "variant_id",
            name="uq_bundle_item_bundle_product_variant"
        ),
    )
    
    # Relationships
    bundle: Mapped["Product"] = relationship(
        "Product",
        foreign_keys=[bundle_id],
        back_populates="bundle_items",
        lazy="select",
    )
    
    product: Mapped["Product"] = relationship(
        "Product",
        foreign_keys=[product_id],
        back_populates="included_in_bundles",
        lazy="select",
    )
    
    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant",
        back_populates="bundle_items",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<BundleItem(id={self.id}, bundle_id={self.bundle_id}, product_id={self.product_id}, quantity={self.quantity})>"