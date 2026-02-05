"""
Authentication endpoints for admin users.

Provides login endpoint that returns JWT token for authenticated users.
Includes cart linking functionality for anonymous users.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.security import create_access_token, verify_password, ACCESS_TOKEN_EXPIRE_HOURS
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse
from app.services import CartService

router = APIRouter()


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    credentials: LoginRequest,
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate admin user and return JWT token.
    
    Includes cart linking functionality:
    - If X-Anonymous-ID header is provided and valid:
      1. Find anonymous cart by anonymous_id
      2. Find user cart by user_id
      3. If both exist: merge carts using CartService.merge_carts()
      4. If only anonymous cart exists: update cart with user_id and clear anonymous_id
      5. If only user cart exists: keep user cart as is
    
    Args:
        credentials: Email and password
        x_anonymous_id: Optional anonymous identifier for cart linking
        db: Database session
        
    Returns:
        JWT token and user information
        
    Raises:
        UnauthorizedException: If credentials are invalid or user is inactive
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()
    
    # Verify user exists and password is correct
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise UnauthorizedException("Invalid email or password")
    
    # Check if user is active
    if not user.is_active:
        raise UnauthorizedException("User account is inactive")
    
    # Handle cart linking if anonymous_id is provided
    if x_anonymous_id and user.storefront_id:
        await _link_anonymous_cart_to_user(
            anonymous_id=x_anonymous_id,
            user_id=user.id,
            storefront_id=user.storefront_id,
            db=db
        )
    
    # Generate JWT token
    access_token = create_access_token(
        user_id=user.id,
        role=user.role,
        storefront_id=user.storefront_id,
    )
    
    # Return token and user info
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,  # Convert hours to seconds
        user=UserResponse.model_validate(user),
    )


async def _link_anonymous_cart_to_user(
    anonymous_id: str,
    user_id: int,
    storefront_id: int,
    db: AsyncSession
) -> None:
    """
    Link anonymous cart to user upon login.
    
    Logic:
    1. Find anonymous cart by anonymous_id and storefront_id
    2. Find user cart by user_id and storefront_id
    3. If both exist: merge carts
    4. If only anonymous cart exists: update with user_id and clear anonymous_id
    5. If only user cart exists: do nothing
    6. If neither exists: do nothing
    
    Args:
        anonymous_id: Anonymous identifier
        user_id: User ID
        storefront_id: Storefront ID
        db: Database session
    """
    cart_service = CartService(db)
    
    try:
        # Try to get anonymous cart
        anonymous_cart = None
        try:
            anonymous_cart = await cart_service.cart_repo.get_by_user_or_anonymous(
                storefront_id=storefront_id,
                anonymous_id=anonymous_id
            )
        except Exception:
            # Anonymous cart not found or error - ignore
            pass
        
        # Try to get user cart
        user_cart = None
        try:
            user_cart = await cart_service.cart_repo.get_by_user_or_anonymous(
                storefront_id=storefront_id,
                user_id=user_id
            )
        except Exception:
            # User cart not found or error - ignore
            pass
        
        if anonymous_cart and user_cart:
            # Both carts exist - merge them
            await cart_service.merge_carts(
                anonymous_cart_id=anonymous_cart.id,
                user_cart_id=user_cart.id
            )
            
        elif anonymous_cart and not user_cart:
            # Only anonymous cart exists - update it with user_id
            await cart_service.cart_repo.update(
                anonymous_cart.id,
                user_id=user_id,
                anonymous_id=None  # Clear anonymous_id
            )
            
        # If only user cart exists or neither exists, do nothing
        
    except Exception as e:
        # Log error but don't fail login
        # In production, you would want to log this properly
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error linking anonymous cart to user: {e}")
