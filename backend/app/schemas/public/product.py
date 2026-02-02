"""
Pydantic schemas for public product endpoints.

Defines request/response models for public product catalog API.
Excludes sensitive/internal fields (cost_price, supplier_id, etc.)
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ========== COMMON SUB-SCHEMAS ==========

class CategorySummary(BaseModel):
    """Summary of a category for product responses."""
    
    id: UUID
    name: str
    slug: str
    
    model_config = ConfigDict(from_attributes=True)


class ProductImage(BaseModel):
    """Product image representation."""
    
    url: str = Field(..., description="Image URL")
    alt: Optional[str] = Field(None, description="Alt text for accessibility")
    position: Optional[int] = Field(default=0, description="Display position")
    
    model_config = ConfigDict(from_attributes=True)


class ProductVariantPublic(BaseModel):
    """Public representation of a product variant."""
    
    id: UUID
    sku: str = Field(..., description="Variant SKU")
    name: str = Field(..., description="Variant name")
    options: Dict[str, Any] = Field(default_factory=dict, description="Variant options (color, size, etc.)")
    price_adjustment: Decimal = Field(default=0, description="Price adjustment from base price")
    stock_status: str = Field(..., description="Stock status: 'in_stock', 'low_stock', 'out_of_stock'")
    image_url: Optional[str] = Field(None, description="Variant-specific image URL")
    
    model_config = ConfigDict(from_attributes=True)


# ========== PRODUCT LIST RESPONSE ==========

class ProductListResponse(BaseModel):
    """Response schema for product list endpoint."""
    
    id: UUID
    name: str = Field(..., description="Product name")
    slug: str = Field(..., description="URL-friendly identifier")
    short_description: Optional[str] = Field(None, description="Brief product description")
    base_price: Decimal = Field(..., description="Base price")
    compare_price: Optional[Decimal] = Field(None, description="Compare/previous price")
    currency: str = Field(default="ARS", description="Currency code")
    product_type: str = Field(..., description="Product type: physical, digital, service, bundle")
    images: List[ProductImage] = Field(default_factory=list, description="Product images")
    category: Optional[CategorySummary] = Field(None, description="Category details")
    stock_status: str = Field(..., description="Overall stock status: 'in_stock', 'low_stock', 'out_of_stock'")
    is_featured: bool = Field(default=False, description="Whether product is featured")
    variants_count: Optional[int] = Field(0, description="Number of variants available")
    
    model_config = ConfigDict(from_attributes=True)


class ProductListPaginated(BaseModel):
    """Paginated response for product list."""
    
    data: List[ProductListResponse]
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


# ========== PRODUCT DETAIL RESPONSE ==========

class ProductDetailResponse(BaseModel):
    """Response schema for product detail endpoint."""
    
    id: UUID
    name: str = Field(..., description="Product name")
    slug: str = Field(..., description="URL-friendly identifier")
    description: Optional[str] = Field(None, description="Full product description")
    short_description: Optional[str] = Field(None, description="Brief product description")
    base_price: Decimal = Field(..., description="Base price")
    compare_price: Optional[Decimal] = Field(None, description="Compare/previous price")
    currency: str = Field(default="ARS", description="Currency code")
    product_type: str = Field(..., description="Product type: physical, digital, service, bundle")
    images: List[ProductImage] = Field(default_factory=list, description="Product images")
    category: Optional[CategorySummary] = Field(None, description="Category details")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Product attributes (JSON)")
    variants: List[ProductVariantPublic] = Field(default_factory=list, description="Product variants")
    stock_status: str = Field(..., description="Overall stock status: 'in_stock', 'low_stock', 'out_of_stock'")
    is_featured: bool = Field(default=False, description="Whether product is featured")
    meta_title: Optional[str] = Field(None, description="SEO meta title")
    meta_description: Optional[str] = Field(None, description="SEO meta description")
    
    model_config = ConfigDict(from_attributes=True)


# ========== FILTER PARAMETERS ==========

class ProductFilters(BaseModel):
    """Query parameters for filtering products."""
    
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")
    category: Optional[str] = Field(None, description="Filter by category slug")
    search: Optional[str] = Field(None, description="Search term for product name/description")
    min_price: Optional[Decimal] = Field(None, ge=0, description="Minimum price filter")
    max_price: Optional[Decimal] = Field(None, ge=0, description="Maximum price filter")
    in_stock: Optional[bool] = Field(None, description="Filter by in-stock status")
    sort: Optional[str] = Field(
        None, 
        description="Sort order: 'price_asc', 'price_desc', 'newest', 'featured'"
    )
    
    model_config = ConfigDict(extra='ignore')