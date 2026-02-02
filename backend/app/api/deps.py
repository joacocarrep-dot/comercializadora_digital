"""
Common dependencies for API endpoints.

Provides reusable dependencies for storefront identification,
database sessions, and other common needs.
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.security import get_current_user, get_current_admin_user
from app.models.storefront import Storefront
from app.models.user import User
from app.services import ProductService, CategoryService, InventoryService


async def get_current_storefront(request: Request) -> Storefront:
    """
    Get the current storefront from request state.
    
    This dependency extracts the storefront that was injected by StorefrontMiddleware.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Current storefront instance
        
    Raises:
        UnauthorizedException: If storefront is not found in request state
    """
    storefront = getattr(request.state, 'storefront', None)
    if not storefront:
        raise UnauthorizedException("Storefront identification required. Include X-API-Key header.")
    
    return storefront


async def get_product_service(
    db: AsyncSession = Depends(get_db),
) -> ProductService:
    """
    Dependency to get ProductService instance.
    
    Args:
        db: Database session
        
    Returns:
        ProductService instance
    """
    return ProductService(db)


async def get_category_service(
    db: AsyncSession = Depends(get_db),
) -> CategoryService:
    """
    Dependency to get CategoryService instance.
    
    Args:
        db: Database session
        
    Returns:
        CategoryService instance
    """
    return CategoryService(db)


async def get_inventory_service(
    db: AsyncSession = Depends(get_db),
) -> InventoryService:
    """
    Dependency to get InventoryService instance.
    
    Args:
        db: Database session
        
    Returns:
        InventoryService instance
    """
    return InventoryService(db)


# Re-export common dependencies from security module
__all__ = [
    "get_current_user",
    "get_current_admin_user",
    "get_current_storefront",
    "get_product_service",
    "get_category_service",
    "get_inventory_service",
    "get_db",
]