"""
Pydantic schemas for ProductVariant endpoints.

Defines request/response models for product variant operations.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductVariantBase(BaseModel):
    """Base schema with common product variant fields."""
    
    sku: str = Field(..., min_length=1, max_length=100, description="Variant SKU")
    name: str = Field(..., min_length=1, max_length=255, description="Variant name")
    options: Dict[str, Any] = Field(default_factory=dict, description="Variant options (color, size, etc.)")
    price_adjustment: Decimal = Field(default=0, max_digits=12, decimal_places=2, description="Price adjustment from base price")
    image_url: Optional[str] = Field(None, description="Variant-specific image URL")
    is_active: bool = Field(default=True, description="Whether variant is active")
    position: int = Field(default=0, description="Display position")


class ProductVariantCreate(ProductVariantBase):
    """Schema for creating a new product variant."""
    
    product_id: UUID = Field(..., description="Parent product ID")
    
    @field_validator('price_adjustment', mode='before')
    @classmethod
    def validate_price_string(cls, v):
        """Accept string prices and convert to Decimal."""
        if isinstance(v, str):
            try:
                return Decimal(v)
            except:
                raise ValueError(f"Invalid price format: {v}")
        return v


class ProductVariantUpdate(BaseModel):
    """Schema for updating an existing product variant (all fields optional)."""
    
    sku: Optional[str] = Field(None, min_length=1, max_length=100)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    options: Optional[Dict[str, Any]] = None
    price_adjustment: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    position: Optional[int] = Field(None, ge=0)
    
    @field_validator('price_adjustment', mode='before')
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


class ProductVariantResponse(ProductVariantBase):
    """Schema for product variant response."""
    
    id: UUID
    product_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ProductVariantListResponse(BaseModel):
    """Schema for paginated product variant list response."""
    
    items: List[ProductVariantResponse]
    total: int
    page: int
    per_page: int
    total_pages: int