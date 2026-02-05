"""
Common dependencies for API endpoints.

Provides reusable dependencies for storefront identification,
database sessions, and other common needs.
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.security import get_current_user, get_current_admin_user, decode_access_token
from app.models.storefront import Storefront
from app.models.user import User
from app.services import ProductService, CategoryService, InventoryService, CartService


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


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Dependency to get current authenticated user if token exists, otherwise None.
    
    Args:
        authorization: Authorization header with Bearer token (optional)
        db: Database session
        
    Returns:
        User instance if authenticated, None otherwise
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    try:
        token = authorization.replace("Bearer ", "")
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        from app.repositories.base import BaseRepository
        user_repo = BaseRepository(User, db)
        user = await user_repo.get_by_id(UUID(user_id))
        
        if not user or not user.is_active:
            return None
        
        return user
    except Exception:
        # If any error occurs (invalid token, expired, etc.), return None
        return None


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


async def get_cart_service(
    db: AsyncSession = Depends(get_db),
) -> CartService:
    """
    Dependency to get CartService instance.
    
    Args:
        db: Database session
        
    Returns:
        CartService instance
    """
    return CartService(db)


# Re-export common dependencies from security module
__all__ = [
    "get_current_user",
    "get_current_user_optional",
    "get_current_admin_user",
    "get_current_storefront",
    "get_product_service",
    "get_category_service",
    "get_inventory_service",
    "get_cart_service",
    "get_db",
]
