"""
Pydantic schemas for Product endpoints.

Defines request/response models for product CRUD operations.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.product import ProductType


class ProductImage(BaseModel):
    """Schema for product image object."""
    
    url: str = Field(..., description="Image URL")
    alt: Optional[str] = Field(None, description="Alt text for accessibility")
    position: Optional[int] = Field(0, description="Display position")


class ProductBase(BaseModel):
    """Base schema with common product fields."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Product name")
    slug: Optional[str] = Field(None, min_length=1, max_length=255, description="URL-friendly identifier")
    sku: str = Field(..., min_length=1, max_length=100, description="Stock keeping unit")
    product_type: ProductType = Field(default=ProductType.PHYSICAL, description="Product type")
    supplier_id: UUID = Field(..., description="Supplier ID")
    category_id: Optional[UUID] = Field(None, description="Category ID")
    description: Optional[str] = Field(None, description="Full product description")
    short_description: Optional[str] = Field(None, max_length=500, description="Brief description")
    base_price: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2, description="Base selling price")
    compare_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2, description="Comparison price")
    cost_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2, description="Cost price")
    currency: str = Field(default="ARS", min_length=3, max_length=3, description="Currency code")
    tax_rate: Decimal = Field(default=0, ge=0, le=100, max_digits=5, decimal_places=2, description="Tax rate percentage")
    images: Optional[List[ProductImage]] = Field(default_factory=list, description="Product images")
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Flexible product attributes")
    meta_title: Optional[str] = Field(None, max_length=255, description="SEO meta title")
    meta_description: Optional[str] = Field(None, max_length=500, description="SEO meta description")
    external_id: Optional[str] = Field(None, max_length=255, description="External supplier ID")
    external_sku: Optional[str] = Field(None, max_length=255, description="External supplier SKU")
    is_active: bool = Field(default=True, description="Whether product is active")
    is_featured: bool = Field(default=False, description="Whether product is featured")


class ProductCreate(ProductBase):
    """Schema for creating a new product."""
    
    @field_validator('base_price', 'compare_price', 'cost_price', mode='before')
    @classmethod
    def validate_price_string(cls, v):
        """Accept string prices and convert to Decimal."""
        if isinstance(v, str):
            try:
                return Decimal(v)
            except:
                raise ValueError(f"Invalid price format: {v}")
        return v


class ProductUpdate(BaseModel):
    """Schema for updating an existing product (all fields optional)."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=255)
    sku: Optional[str] = Field(None, min_length=1, max_length=100)
    product_type: Optional[ProductType] = None
    supplier_id: Optional[UUID] = None
    category_id: Optional[UUID] = Field(None)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)
    base_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2)
    compare_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2)
    cost_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    images: Optional[List[ProductImage]] = None
    attributes: Optional[Dict[str, Any]] = None
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)
    external_id: Optional[str] = Field(None, max_length=255)
    external_sku: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    
    @field_validator('base_price', 'compare_price', 'cost_price', mode='before')
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


class ProductResponse(ProductBase):
    """Schema for product response."""
    
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    """Schema for paginated product list response."""
    
    items: List[ProductResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ProductVariantBase(BaseModel):
    """Base schema for product variant fields."""
    
    sku: str = Field(..., min_length=1, max_length=100, description="Variant SKU")
    name: str = Field(..., min_length=1, max_length=255, description="Variant name")
    options: Dict[str, Any] = Field(default_factory=dict, description="Variant options (color, size, etc.)")
    price_adjustment: Decimal = Field(default=0, max_digits=12, decimal_places=2, description="Price adjustment from base price")
    image_url: Optional[str] = Field(None, description="Variant-specific image URL")
    is_active: bool = Field(default=True, description="Whether variant is active")
    position: int = Field(default=0, description="Display position")


class ProductImportRequest(BaseModel):
    """Schema for product import request."""
    
    supplier_id: UUID = Field(..., description="Supplier ID")
    file_name: str = Field(..., description="Uploaded file name")
    file_url: str = Field(..., description="File storage URL")
    import_type: str = Field("products", description="Import type")


class ProductImportResponse(BaseModel):
    """Schema for product import response."""
    
    id: UUID
    supplier_id: UUID
    import_type: str
    file_name: str
    file_url: str
    status: str
    total_rows: int
    processed_rows: int
    success_count: int
    error_count: int
    errors: List[Dict[str, Any]]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class StorefrontProductAssignment(BaseModel):
    """Schema for assigning product to storefront."""
    
    custom_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2, description="Custom price override")
    custom_compare_price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2, description="Custom compare price override")
    is_active: bool = Field(default=True, description="Whether product is active in storefront")
    is_featured: bool = Field(default=False, description="Whether product is featured in storefront")
    position: int = Field(default=0, description="Display position in storefront")
    storefront_category_id: Optional[UUID] = Field(None, description="Storefront-specific category override")


class InventoryUpdate(BaseModel):
    """Schema for inventory stock update."""
    
    quantity: int = Field(..., ge=0, description="New quantity (use override mode)")
    quantity_change: Optional[int] = Field(None, description="Quantity to add/subtract (use incremental mode)")
    allow_negative: bool = Field(default=False, description="Allow negative stock after update")
    override: bool = Field(default=True, description="Whether to set quantity directly or add/subtract")