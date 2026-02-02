"""
Pydantic schemas for Category endpoints.

Defines request/response models for category CRUD operations.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    """Base schema with common category fields."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Category name")
    slug: Optional[str] = Field(None, min_length=1, max_length=255, description="URL-friendly identifier")
    parent_id: Optional[UUID] = Field(None, description="Parent category ID")
    description: Optional[str] = Field(None, description="Category description")
    image_url: Optional[str] = Field(None, max_length=500, description="Category image URL")
    position: int = Field(default=0, ge=0, description="Display position")
    is_active: bool = Field(default=True, description="Whether category is active")


class CategoryCreate(CategoryBase):
    """Schema for creating a new category."""
    pass


class CategoryUpdate(BaseModel):
    """Schema for updating an existing category (all fields optional)."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[UUID] = Field(None)
    description: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=500)
    position: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    
    model_config = ConfigDict(extra='ignore')


class CategoryResponse(CategoryBase):
    """Schema for category response."""
    
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CategoryTreeResponse(BaseModel):
    """Schema for hierarchical category tree response."""
    
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    image_url: Optional[str]
    position: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    children: List["CategoryTreeResponse"]
    product_count: Optional[int] = Field(default=0, description="Number of products in category")
    
    model_config = ConfigDict(from_attributes=True)


# Update forward reference for recursive type
CategoryTreeResponse.model_rebuild()


class CategoryListResponse(BaseModel):
    """Schema for paginated category list response."""
    
    items: List[CategoryResponse]
    total: int
    page: int
    per_page: int
    total_pages: int