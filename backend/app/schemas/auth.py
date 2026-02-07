"""
Pydantic schemas for authentication endpoints.

Defines request/response models for login and JWT token operations.
"""
from enum import Enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole, UserType


class LoginRequest(BaseModel):
    """Schema for login request."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class UserResponse(BaseModel):
    """Schema for user information in token response."""
    
    id: UUID
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    user_type: UserType
    storefront_id: Optional[UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email_verified: bool = False
    phone_verified: bool = False
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Schema for complete login response with token and user info."""
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="Authenticated user information")


# ===== Customer Authentication Schemas =====

class OTPRequest(BaseModel):
    """Schema for OTP code request."""
    
    email: Optional[EmailStr] = Field(None, description="Email address for OTP")
    phone: Optional[str] = Field(None, description="Phone number for OTP (E.164 format)")
    
    class Config:
        schema_extra = {
            "example": {
                "email": "customer@example.com"
            }
        }


class OTPResponse(BaseModel):
    """Schema for OTP code response."""
    
    message: str = Field(..., description="Status message")
    contact: Optional[str] = Field(None, description="Email or phone where code was sent")
    contact_type: Optional[str] = Field(None, description="Type of contact: email or phone")
    channel: str = Field(..., description="Channel used: whatsapp, email, or sms")
    expires_in: int = Field(..., description="Code expiration time in seconds")
    purpose: str = Field(default="login", description="Purpose of OTP code")
    code_id: Optional[str] = Field(None, description="Internal code ID for debugging")
    simulated: bool = Field(default=True, description="Indicates if sending was simulated")


class OTPVerifyRequest(BaseModel):
    """Schema for OTP code verification."""
    
    email: Optional[EmailStr] = Field(None, description="Email address used for OTP")
    phone: Optional[str] = Field(None, description="Phone number used for OTP")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")
    
    class Config:
        schema_extra = {
            "example": {
                "email": "customer@example.com",
                "code": "123456"
            }
        }


class OTPVerifyResponse(BaseModel):
    """Schema for OTP verification response."""
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="Authenticated user information")
    cart_linked: bool = Field(default=False, description="Whether anonymous cart was linked")


class OAuthProvider(str, Enum):
    """Enum for OAuth providers."""
    
    GOOGLE = "google"
    FACEBOOK = "facebook"
    APPLE = "apple"


class OAuthResponse(BaseModel):
    """Schema for OAuth login response."""
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="Authenticated user information")
    cart_linked: bool = Field(default=False, description="Whether anonymous cart was linked")


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""
    
    refresh_token: str = Field(..., description="Refresh token string")


class ProfileUpdateRequest(BaseModel):
    """Schema for updating user profile."""
    
    first_name: Optional[str] = Field(None, min_length=1, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Last name")
    email: Optional[EmailStr] = Field(None, description="New email address (requires verification)")
    phone: Optional[str] = Field(None, description="New phone number (requires verification)")


class CustomerTokenPayload(BaseModel):
    """Schema for customer JWT token payload."""
    
    sub: UUID = Field(..., description="User ID")
    storefront_id: UUID = Field(..., description="Storefront ID")
    user_type: UserType = Field(..., description="User type (customer)")
    exp: int = Field(..., description="Expiration timestamp")
