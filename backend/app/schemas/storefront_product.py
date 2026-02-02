"""
Pydantic schemas for StorefrontProduct endpoints.

Defines request/response models for storefront-product assignment operations.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StorefrontProductBase(BaseModel):
    """Base schema with common storefront product fields."""
    
    custom_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2, description="Custom price override")
    custom_compare_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2, description="Custom compare price override")
    is_active: bool = Field(default=True, description="Whether product is active in storefront")
    is_featured: bool = Field(default=False, description="Whether product is featured in storefront")
    position: int = Field(default=0, description="Display position in storefront")
    storefront_category_id: Optional[UUID] = Field(None, description="Storefront-specific category override")


class StorefrontProductCreate(StorefrontProductBase):
    """Schema for creating a new storefront product assignment."""
    
    storefront_id: UUID = Field(..., description="Storefront ID")
    product_id: UUID = Field(..., description="Product ID")
    
    @field_validator('custom_price', 'custom_compare_price', mode='before')
    @classmethod
    def validate_price_string(cls, v):
        """Accept string prices and convert to Decimal."""
        if isinstance(v, str):
            try:
                return Decimal(v)
            except:
                raise ValueError(f"Invalid price format: {v}")
        return v


class StorefrontProductUpdate(BaseModel):
    """Schema for updating an existing storefront product assignment."""
    
    custom_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2)
    custom_compare_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2)
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    position: Optional[int] = Field(None, ge=0)
    storefront_category_id: Optional[UUID] = Field(None)
    
    @field_validator('custom_price', 'custom_compare_price', mode='before')
    @classmethod
    def validate_price_string(cls, v):
        """Accept string prices and convert to Decimal."""
        if isinstance(v, str):
            try:
                return Decimal(v)
            except:
                raise ValueError(f"Invalid price format: {v}")
        return v
    
    model_config = ConfigDict(extra='ignore')


class StorefrontProductResponse(StorefrontProductBase):
    """Schema for storefront product response."""
    
    id: UUID
    storefront_id: UUID
    product_id: UUID
    created_at: datetime
    
    # Relationship fields
    storefront: Optional["StorefrontResponse"] = Field(None, description="Storefront details")
    product: Optional["ProductResponse"] = Field(None, description="Product details")
    storefront_category: Optional["CategoryResponse"] = Field(None, description="Category details")
    
    model_config = ConfigDict(from_attributes=True)


class StorefrontProductListResponse(BaseModel):
    """Schema for paginated storefront product list response."""
    
    items: List[StorefrontProductResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


# Import related schemas to avoid circular imports
from app.schemas.storefront import StorefrontResponse
from app.schemas.product import ProductResponse
from app.schemas.category import CategoryResponse

# Update forward references
StorefrontProductResponse.model_rebuild()