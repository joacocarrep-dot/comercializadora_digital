"""
Public API endpoints for storefronts.

This package contains endpoints accessible to storefronts via API key authentication.
Includes product catalog, categories, cart, authentication, checkout, orders, and other public-facing functionality.
"""

# Import routers to expose them
from app.api.v1.public.products import router as products_router
from app.api.v1.public.categories import router as categories_router
from app.api.v1.public.cart import router as cart_router
from app.api.v1.public.auth import router as auth_router
from app.api.v1.public.checkout import router as checkout_router
from app.api.v1.public.orders import router as orders_router

__all__ = ["products_router", "categories_router", "cart_router", "auth_router", "checkout_router", "orders_router"]
