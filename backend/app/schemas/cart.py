"""
Pydantic schemas for cart endpoints.

Defines request/response models for cart operations in the public API.
Includes support for both authenticated users and anonymous shopping.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ========== SUB-SCHEMAS ==========

class ProductSummary(BaseModel):
    """Summary of a product for cart item responses."""
    
    id: UUID
    name: str = Field(..., description="Product name")
    slug: str = Field(..., description="URL-friendly identifier")
    image_url: Optional[str] = Field(None, description="Main product image URL")
    
    model_config = ConfigDict(from_attributes=True)


class VariantSummary(BaseModel):
    """Summary of a product variant for cart item responses."""
    
    id: UUID
    name: str = Field(..., description="Variant name")
    sku: str = Field(..., description="Variant SKU")
    
    model_config = ConfigDict(from_attributes=True)


class CartItemResponse(BaseModel):
    """Response schema for a cart item."""
    
    id: UUID
    product: ProductSummary = Field(..., description="Product details")
    variant: Optional[VariantSummary] = Field(None, description="Variant details, if applicable")
    quantity: int = Field(..., ge=1, description="Item quantity")
    unit_price: Decimal = Field(..., ge=0, description="Current unit price")
    total_price: Decimal = Field(..., ge=0, description="Total price (unit_price * quantity)")
    price_changed: bool = Field(
        default=False,
        description="Whether price has changed since item was added to cart"
    )
    product_active: bool = Field(
        default=True,
        description="Whether the product is still active and available"
    )
    added_at: str = Field(..., description="ISO 8601 timestamp when item was added")
    
    model_config = ConfigDict(from_attributes=True)


# ========== CART RESPONSE ==========

class CartResponse(BaseModel):
    """Response schema for cart retrieval."""
    
    id: UUID
    items: List[CartItemResponse] = Field(default_factory=list, description="Cart items")
    subtotal: Decimal = Field(..., ge=0, description="Cart subtotal (sum of item totals)")
    currency: str = Field(default="ARS", description="Currency code")
    item_count: int = Field(..., ge=0, description="Total number of items in cart")
    storefront_id: UUID = Field(..., description="Storefront ID")
    user_id: Optional[UUID] = Field(None, description="User ID if authenticated")
    anonymous_id: Optional[str] = Field(None, description="Anonymous ID if guest user")
    
    model_config = ConfigDict(from_attributes=True)


# ========== REQUEST SCHEMAS ==========

class AddItemRequest(BaseModel):
    """Request schema for adding an item to cart."""
    
    product_id: UUID = Field(..., description="ID of the product to add")
    variant_id: Optional[UUID] = Field(None, description="Optional variant ID")
    quantity: int = Field(default=1, ge=1, description="Quantity to add (default: 1)")
    
    model_config = ConfigDict(extra='forbid')


class UpdateItemRequest(BaseModel):
    """Request schema for updating cart item quantity."""
    
    quantity: int = Field(..., ge=1, description="New quantity (must be positive)")
    
    model_config = ConfigDict(extra='forbid')


# ========== HEADER/QUERY PARAMETERS ==========

class CartIdentificationHeaders(BaseModel):
    """Headers for cart identification (user or anonymous)."""
    
    x_anonymous_id: Optional[str] = Field(
        None,
        alias="X-Anonymous-ID",
        description="Anonymous identifier for guest users"
    )
    
    model_config = ConfigDict(extra='ignore')


# ========== VALIDATION RESPONSE ==========

class PriceChangedItem(BaseModel):
    """Details of an item with price change."""
    
    cart_item_id: UUID
    product_id: UUID
    variant_id: Optional[UUID]
    old_price: Decimal
    new_price: Decimal
    quantity: int
    price_difference: Decimal
    total_price_difference: Decimal


class OutOfStockItem(BaseModel):
    """Details of an out-of-stock item."""
    
    cart_item_id: UUID
    product_id: UUID
    variant_id: Optional[UUID]
    quantity_in_cart: int
    available_qty: int
    is_backorder_allowed: bool


class CartValidationResponse(BaseModel):
    """Response schema for cart validation."""
    
    cart_id: UUID
    items_with_price_changes: List[PriceChangedItem] = Field(default_factory=list)
    items_out_of_stock: List[OutOfStockItem] = Field(default_factory=list)
    total_price_difference: Decimal = Field(default=0, description="Total price difference across all items")
    is_valid: bool = Field(default=True, description="Whether cart is valid (no out-of-stock items)")