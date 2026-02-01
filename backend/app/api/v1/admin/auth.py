"""
Authentication endpoints for admin users.

Provides login endpoint that returns JWT token for authenticated users.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.security import create_access_token, verify_password, ACCESS_TOKEN_EXPIRE_HOURS
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate admin user and return JWT token.
    
    Args:
        credentials: Email and password
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
