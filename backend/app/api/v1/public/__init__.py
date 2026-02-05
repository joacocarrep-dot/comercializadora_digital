"""
Public API endpoints for storefronts.

This package contains endpoints accessible to storefronts via API key authentication.
Includes product catalog, categories, cart, and other public-facing functionality.
"""

# Import routers to expose them
from app.api.v1.public.products import router as products_router
from app.api.v1.public.categories import router as categories_router
from app.api.v1.public.cart import router as cart_router

__all__ = ["products_router", "categories_router", "cart_router"]
