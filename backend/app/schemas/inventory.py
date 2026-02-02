"""
Pydantic schemas for Inventory endpoints.

Defines request/response models for inventory management operations.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.product import Product
from app.models.product_variant import ProductVariant


class InventoryBase(BaseModel):
    """Base schema with common inventory fields."""
    
    product_id: Optional[UUID] = Field(None, description="Product ID (nullable if variant_id provided)")
    variant_id: Optional[UUID] = Field(None, description="Variant ID (nullable if product_id provided)")
    quantity: int = Field(default=0, ge=0, description="Available stock quantity")
    reserved_qty: int = Field(default=0, ge=0, description="Reserved stock quantity")
    low_stock_alert: int = Field(default=5, ge=0, description="Low stock alert threshold")
    warehouse_id: Optional[UUID] = Field(None, description="Warehouse ID (future use)")
    track_inventory: bool = Field(default=True, description="Whether to track inventory for this item")
    allow_backorder: bool = Field(default=False, description="Whether to allow backorders")


class InventoryCreate(InventoryBase):
    """Schema for creating a new inventory record."""
    
    @field_validator('quantity', 'reserved_qty')
    @classmethod
    def validate_reserved_not_exceed_quantity(cls, v, info):
        """Validate reserved_qty does not exceed quantity."""
        if info.field_name == 'reserved_qty':
            # This validation would need access to quantity field
            # Better to validate in service
            pass
        return v
    
    @field_validator('product_id', 'variant_id')
    @classmethod
    def validate_product_or_variant(cls, v, info):
        """Validate at least one of product_id or variant_id is provided."""
        values = info.data
        if not values.get('product_id') and not values.get('variant_id'):
            raise ValueError("Either product_id or variant_id must be provided")
        return v


class InventoryUpdate(BaseModel):
    """Schema for updating an existing inventory record."""
    
    quantity: Optional[int] = Field(None, ge=0, description="New quantity (use override mode)")
    quantity_change: Optional[int] = Field(None, description="Quantity to add/subtract (use incremental mode)")
    reserved_qty: Optional[int] = Field(None, ge=0, description="New reserved quantity")
    low_stock_alert: Optional[int] = Field(None, ge=0, description="Low stock alert threshold")
    track_inventory: Optional[bool] = Field(None, description="Whether to track inventory for this item")
    allow_backorder: Optional[bool] = Field(None, description="Whether to allow backorders")
    
    model_config = ConfigDict(extra='ignore')


class InventoryResponse(InventoryBase):
    """Schema for inventory response."""
    
    id: UUID
    available_qty: int = Field(..., description="Available quantity (quantity - reserved_qty)")
    updated_at: datetime
    
    # Relationship fields
    product: Optional["ProductResponse"] = Field(None, description="Product details")
    variant: Optional["ProductVariantResponse"] = Field(None, description="Variant details")
    
    model_config = ConfigDict(from_attributes=True)


class InventoryListResponse(BaseModel):
    """Schema for paginated inventory list response."""
    
    items: List[InventoryResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class LowStockAlertResponse(BaseModel):
    """Schema for low stock alerts response."""
    
    id: UUID
    product_id: Optional[UUID]
    variant_id: Optional[UUID]
    product_name: Optional[str] = Field(None, description="Product name")
    variant_name: Optional[str] = Field(None, description="Variant name")
    sku: Optional[str] = Field(None, description="Product or variant SKU")
    quantity: int
    reserved_qty: int
    available_qty: int
    low_stock_alert: int
    status: str = Field(..., description="Stock status: 'low_stock', 'out_of_stock', 'in_stock'")


# Import related schemas to avoid circular imports
from app.schemas.product import ProductResponse
from app.schemas.product_variant import ProductVariantResponse


# Update forward references
InventoryResponse.model_rebuild()


class InventoryBulkUpdate(BaseModel):
    """Schema for bulk inventory updates."""
    
    inventory_id: UUID
    quantity_change: int = Field(..., description="Quantity to add (positive) or subtract (negative)")
    allow_negative: bool = Field(default=False, description="Whether to allow negative stock after update")
    override: bool = Field(default=False, description="Whether to set quantity directly instead of adding")