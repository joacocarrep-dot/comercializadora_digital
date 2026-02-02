"""
Models package initialization.

Imports all models to ensure they are registered with SQLAlchemy's metadata
for Alembic autogeneration and ORM operations.
"""
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.storefront import Storefront
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.models.product import Product, ProductType
from app.models.category import Category
from app.models.product_variant import ProductVariant
from app.models.inventory import Inventory
from app.models.bundle_item import BundleItem
from app.models.digital_asset import DigitalAsset
from app.models.storefront_product import StorefrontProduct
from app.models.product_import import ProductImport

__all__ = [
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "Supplier",
    "Storefront",
    "User",
    "UserRole",
    "Product",
    "ProductType",
    "Category",
    "ProductVariant",
    "Inventory",
    "BundleItem",
    "DigitalAsset",
    "StorefrontProduct",
    "ProductImport",
]
