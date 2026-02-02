"""
Pydantic schemas for public category endpoints.

Defines request/response models for public category API.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ========== CATEGORY TREE RESPONSE ==========

class CategoryTreeNode(BaseModel):
    """Node in hierarchical category tree for public API."""
    
    id: UUID
    name: str = Field(..., description="Category name")
    slug: str = Field(..., description="URL-friendly identifier")
    description: Optional[str] = Field(None, description="Category description")
    image_url: Optional[str] = Field(None, description="Category image URL")
    position: int = Field(default=0, description="Display position")
    children: List["CategoryTreeNode"] = Field(default_factory=list, description="Child categories")
    product_count: Optional[int] = Field(default=0, description="Number of products in category")
    
    model_config = ConfigDict(from_attributes=True)


# Update forward reference for recursive type
CategoryTreeNode.model_rebuild()


class CategoryTreeResponse(BaseModel):
    """Response schema for category tree endpoint."""
    
    data: List[CategoryTreeNode] = Field(default_factory=list, description="Root categories with nested children")
    
    model_config = ConfigDict(from_attributes=True)


# ========== FLAT CATEGORY LIST RESPONSE ==========

class CategoryFlatResponse(BaseModel):
    """Flat category representation for simpler list views."""
    
    id: UUID
    name: str = Field(..., description="Category name")
    slug: str = Field(..., description="URL-friendly identifier")
    description: Optional[str] = Field(None, description="Category description")
    image_url: Optional[str] = Field(None, description="Category image URL")
    position: int = Field(default=0, description="Display position")
    parent_id: Optional[UUID] = Field(None, description="Parent category ID")
    product_count: Optional[int] = Field(default=0, description="Number of products in category")
    
    model_config = ConfigDict(from_attributes=True)


class CategoryListPaginated(BaseModel):
    """Paginated response for flat category list."""
    
    data: List[CategoryFlatResponse]
    pagination: Dict[str, Any] = Field(
        default_factory=lambda: {
            "page": 1,
            "per_page": 20,
            "total": 0,
            "total_pages": 0,
            "has_next": False,
            "has_prev": False
        },
        description="Pagination metadata"
    )


# ========== CATEGORY DETAIL RESPONSE ==========

class CategoryDetailResponse(BaseModel):
    """Detailed category information for single category endpoint."""
    
    id: UUID
    name: str = Field(..., description="Category name")
    slug: str = Field(..., description="URL-friendly identifier")
    description: Optional[str] = Field(None, description="Category description")
    image_url: Optional[str] = Field(None, description="Category image URL")
    position: int = Field(default=0, description="Display position")
    parent_id: Optional[UUID] = Field(None, description="Parent category ID")
    parent: Optional["CategoryFlatResponse"] = Field(None, description="Parent category details")
    children: List[CategoryFlatResponse] = Field(default_factory=list, description="Immediate child categories")
    product_count: Optional[int] = Field(default=0, description="Number of products in category")
    is_active: bool = Field(default=True, description="Whether category is active")
    
    model_config = ConfigDict(from_attributes=True)