"""
Product model for managing products in the catalog.

Supports physical, digital, service, and bundle product types with
flexible JSONB attributes and images storage.
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ProductType(str, enum.Enum):
    """Product type enumeration."""
    
    PHYSICAL = "physical"
    DIGITAL = "digital"
    SERVICE = "service"
    BUNDLE = "bundle"


class Product(Base, UUIDMixin, TimestampMixin):
    """
    Product entity representing a catalog product.
    
    Attributes:
        supplier_id: Foreign key to supplier
        external_id: External identifier from supplier system
        external_sku: External SKU from supplier
        product_type: Type of product (physical, digital, service, bundle)
        category_id: Foreign key to category (nullable)
        sku: Unique stock keeping unit
        name: Product display name
        slug: Unique URL-friendly identifier
        description: Full product description
        short_description: Brief product description
        base_price: Base selling price
        compare_price: Comparison price (e.g., MSRP)
        cost_price: Cost price for margin calculation
        currency: Currency code (default: ARS)
        tax_rate: Tax rate percentage
        images: JSONB array of product images
        attributes: JSONB flexible product attributes
        meta_title: SEO meta title
        meta_description: SEO meta description
        is_active: Whether product is active
        is_featured: Whether product is featured
        last_synced_at: Last synchronization timestamp
        sync_status: Synchronization status
    """
    
    __tablename__ = "products"
    
    # Foreign keys
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    external_sku: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    product_type: Mapped[ProductType] = mapped_column(
        Enum(ProductType, name="product_type", native_enum=False),
        nullable=False,
        index=True,
    )
    
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    sku: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    short_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    base_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    
    compare_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    
    cost_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        default="ARS",
        nullable=False,
    )
    
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=0,
        nullable=False,
    )
    
    images: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )
    
    attributes: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    
    meta_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    meta_description: Mapped[Optional[str]] = mapped_column(
        String(500),
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
    
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )
    
    sync_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("supplier_id", "external_id", name="uq_supplier_external_id"),
        UniqueConstraint("supplier_id", "sku", name="uq_supplier_sku"),
    )
    
    # Relationships
    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        back_populates="products",
        lazy="select",
    )
    
    category: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="products",
        lazy="select",
    )
    
    variants: Mapped[list["ProductVariant"]] = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    inventory_records: Mapped[list["Inventory"]] = relationship(
        "Inventory",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    bundle_items: Mapped[list["BundleItem"]] = relationship(
        "BundleItem",
        foreign_keys="[BundleItem.bundle_id]",
        back_populates="bundle",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    included_in_bundles: Mapped[list["BundleItem"]] = relationship(
        "BundleItem",
        foreign_keys="[BundleItem.product_id]",
        back_populates="product",
        lazy="select",
    )
    
    digital_assets: Mapped[list["DigitalAsset"]] = relationship(
        "DigitalAsset",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    storefront_products: Mapped[list["StorefrontProduct"]] = relationship(
        "StorefrontProduct",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku={self.sku}, name={self.name}, type={self.product_type})>"
