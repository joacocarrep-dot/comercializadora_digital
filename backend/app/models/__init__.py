"""
Models package initialization.

Imports all models to ensure they are registered with SQLAlchemy's metadata
for Alembic autogeneration and ORM operations.
"""
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.storefront import Storefront
from app.models.supplier import Supplier
from app.models.user import User, UserRole, UserType
from app.models.product import Product, ProductType
from app.models.category import Category
from app.models.product_variant import ProductVariant
from app.models.inventory import Inventory
from app.models.bundle_item import BundleItem
from app.models.digital_asset import DigitalAsset
from app.models.storefront_product import StorefrontProduct
from app.models.product_import import ProductImport
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.otp_code import OTPCode, OTPPurpose
from app.models.oauth_connection import OAuthConnection, OAuthProvider
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.stock_reservation import StockReservation, StockReservationStatus

__all__ = [
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "Supplier",
    "Storefront",
    "User",
    "UserRole",
    "UserType",
    "Product",
    "ProductType",
    "Category",
    "ProductVariant",
    "Inventory",
    "BundleItem",
    "DigitalAsset",
    "StorefrontProduct",
    "ProductImport",
    "Cart",
    "CartItem",
    "OTPCode",
    "OTPPurpose",
    "OAuthConnection",
    "OAuthProvider",
    "Order",
    "OrderStatus",
    "OrderItem",
    "OrderStatusHistory",
    "StockReservation",
    "StockReservationStatus",
]
