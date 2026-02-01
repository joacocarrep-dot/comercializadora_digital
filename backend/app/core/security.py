"""
Security utilities for authentication and authorization.

Provides JWT token generation/validation, password hashing,
and FastAPI dependencies for protected endpoints.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.models.user import User, UserRole
from app.repositories.base import BaseRepository

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: UUID,
    role: UserRole,
    storefront_id: Optional[UUID] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User UUID
        role: User role
        storefront_id: Optional storefront UUID for scoped access
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode = {
        "sub": str(user_id),
        "role": role.value,
        "storefront_id": str(storefront_id) if storefront_id else None,
        "exp": expire,
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        UnauthorizedException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise UnauthorizedException("Invalid or expired token")


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        authorization: Authorization header with Bearer token
        db: Database session
        
    Returns:
        Current user instance
        
    Raises:
        UnauthorizedException: If token is missing, invalid, or user not found
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Invalid token payload")
    
    # Get user from database
    user_repo = BaseRepository(User, db)
    user = await user_repo.get_by_id(UUID(user_id))
    
    if not user or not user.is_active:
        raise UnauthorizedException("User not found or inactive")
    
    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to ensure current user has admin or superadmin role.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user if they have admin privileges
        
    Raises:
        UnauthorizedException: If user doesn't have admin privileges
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise UnauthorizedException("Admin privileges required")
    
    return current_user


async def get_current_superadmin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to ensure current user has superadmin role.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user if they have superadmin privileges
        
    Raises:
        UnauthorizedException: If user doesn't have superadmin privileges
    """
    if current_user.role != UserRole.SUPERADMIN:
        raise UnauthorizedException("Superadmin privileges required")
    
    return current_user
