"""
Pydantic schemas for Storefront endpoints.

Defines request/response models for storefront CRUD operations.
Note: API keys are only exposed in the creation response.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StorefrontBase(BaseModel):
    """Base schema with common storefront fields."""
    
    code: str = Field(..., min_length=1, max_length=50, description="Unique storefront code")
    name: str = Field(..., min_length=1, max_length=255, description="Storefront name")
    domain: Optional[str] = Field(None, max_length=255, description="Domain name")
    config: Optional[dict] = Field(default_factory=dict, description="General configuration")
    base_currency: str = Field(default="ARS", max_length=3, description="Base currency code")
    payment_config: Optional[dict] = Field(default_factory=dict, description="Payment gateway config")
    ai_config: Optional[dict] = Field(default_factory=dict, description="AI assistant config")
    is_active: bool = Field(default=True, description="Whether storefront is active")


class StorefrontCreate(StorefrontBase):
    """Schema for creating a new storefront."""
    pass


class StorefrontUpdate(BaseModel):
    """Schema for updating an existing storefront (all fields optional)."""
    
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    config: Optional[dict] = None
    base_currency: Optional[str] = Field(None, max_length=3)
    payment_config: Optional[dict] = None
    ai_config: Optional[dict] = None
    is_active: Optional[bool] = None


class StorefrontResponse(StorefrontBase):
    """Schema for storefront response (without API credentials)."""
    
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StorefrontCreateResponse(StorefrontResponse):
    """
    Schema for storefront creation response.
    
    IMPORTANT: This is the ONLY time API credentials are exposed.
    They should be saved by the client immediately.
    """
    
    api_key: str = Field(..., description="Plain text API key (save immediately!)")
    api_secret: str = Field(..., description="Plain text API secret (save immediately!)")


class StorefrontListResponse(BaseModel):
    """Schema for paginated storefront list response."""
    
    items: list[StorefrontResponse]
    total: int
    skip: int
    limit: int
