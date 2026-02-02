"""
StorefrontProduct model for managing product assignments to storefronts.

Represents the N:M relationship between storefronts and products with
custom pricing, activation, and positioning per storefront.
"""
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class StorefrontProduct(Base, UUIDMixin, TimestampMixin):
    """
    StorefrontProduct entity representing product assignment to a storefront.
    
    Attributes:
        storefront_id: Foreign key to storefront
        product_id: Foreign key to product
        custom_price: Custom price override for this storefront
        custom_compare_price: Custom compare price override
        is_active: Whether product is active in this storefront
        is_featured: Whether product is featured in this storefront
        position: Position for ordering products in this storefront
        storefront_category_id: Optional category override for this storefront
    """
    
    __tablename__ = "storefront_products"
    
    # Foreign keys
    storefront_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storefronts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    custom_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    
    custom_compare_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    position: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        index=True,
    )
    
    storefront_category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "storefront_id", "product_id",
            name="uq_storefront_product"
        ),
    )
    
    # Relationships
    storefront: Mapped["Storefront"] = relationship(
        "Storefront",
        back_populates="storefront_products",
        lazy="select",
    )
    
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="storefront_products",
        lazy="select",
    )
    
    storefront_category: Mapped[Optional["Category"]] = relationship(
        "Category",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<StorefrontProduct(id={self.id}, storefront_id={self.storefront_id}, product_id={self.product_id}, is_active={self.is_active})>"