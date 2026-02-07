"""
Pydantic schemas for order endpoints.

Defines request/response models for order operations in the public API.
Includes order creation, retrieval, and management.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ========== ENUMS ==========

class OrderStatus(str, Enum):
    """Order status enum."""
    CREATED = "created"
    VALIDATING_STOCK = "validating_stock"
    RESERVED = "reserved"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ========== SUB-SCHEMAS ==========

class AddressSchema(BaseModel):
    """Schema for shipping/billing addresses."""
    
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    address_line1: str = Field(..., min_length=1, max_length=200, description="Street address")
    address_line2: Optional[str] = Field(None, max_length=200, description="Apartment, suite, etc.")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    state: Optional[str] = Field(None, max_length=100, description="State/province")
    postal_code: str = Field(..., min_length=1, max_length=20, description="Postal/ZIP code")
    country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")
    phone: Optional[str] = Field(None, max_length=30, description="Phone number")
    email: Optional[str] = Field(None, max_length=255, description="Email address")
    
    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Validate country code is uppercase 2 letters."""
        if not v or len(v) != 2 or not v.isalpha():
            raise ValueError("Country must be a 2-letter ISO country code")
        return v.upper()
    
    model_config = ConfigDict(from_attributes=True)


class OrderItemResponse(BaseModel):
    """Response schema for an order item."""
    
    id: UUID
    product_id: UUID = Field(..., description="Product ID")
    product_name: str = Field(..., description="Product name at time of order")
    product_sku: str = Field(..., description="Product SKU at time of order")
    variant_id: Optional[UUID] = Field(None, description="Variant ID")
    variant_name: Optional[str] = Field(None, description="Variant name at time of order")
    variant_sku: Optional[str] = Field(None, description="Variant SKU at time of order")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    unit_price: Decimal = Field(..., ge=0, description="Unit price at time of order")
    total_price: Decimal = Field(..., ge=0, description="Total price (unit_price * quantity)")
    
    model_config = ConfigDict(from_attributes=True)


class OrderStatusHistoryResponse(BaseModel):
    """Response schema for order status history."""
    
    id: UUID
    from_status: OrderStatus = Field(..., description="Previous status")
    to_status: OrderStatus = Field(..., description="New status")
    reason: Optional[str] = Field(None, description="Reason for status change")
    notes: Optional[str] = Field(None, description="Additional notes")
    changed_by: Optional[UUID] = Field(None, description="User ID who changed the status")
    changed_at: datetime = Field(..., description="When the status was changed")
    
    model_config = ConfigDict(from_attributes=True)


class StockReservationSummary(BaseModel):
    """Summary of a stock reservation."""
    
    id: UUID
    inventory_id: UUID = Field(..., description="Inventory ID")
    quantity: int = Field(..., ge=1, description="Quantity reserved")
    expires_at: datetime = Field(..., description="When reservation expires")
    status: str = Field(..., description="Reservation status (active/released/confirmed)")
    
    model_config = ConfigDict(from_attributes=True)


# ========== ORDER RESPONSE ==========

class OrderResponse(BaseModel):
    """Response schema for order details."""
    
    id: UUID
    order_number: str = Field(..., description="Unique order number")
    storefront_id: UUID = Field(..., description="Storefront ID")
    user_id: Optional[UUID] = Field(None, description="User ID if authenticated")
    
    status: OrderStatus = Field(..., description="Current order status")
    
    # Monetary amounts
    subtotal: Decimal = Field(..., ge=0, description="Subtotal (sum of order items)")
    shipping_amount: Decimal = Field(..., ge=0, description="Shipping cost")
    tax_amount: Decimal = Field(..., ge=0, description="Tax amount")
    total: Decimal = Field(..., ge=0, description="Total amount (subtotal + shipping + tax)")
    currency: str = Field(default="ARS", description="Currency code")
    
    # Addresses
    shipping_address: Optional[Dict[str, Any]] = Field(None, description="Shipping address JSON")
    billing_address: Optional[Dict[str, Any]] = Field(None, description="Billing address JSON")
    
    # Timestamps
    created_at: datetime = Field(..., description="When order was created")
    updated_at: datetime = Field(..., description="When order was last updated")
    reserved_at: Optional[datetime] = Field(None, description="When stock was reserved")
    reservation_expires_at: Optional[datetime] = Field(
        None, 
        description="When reservation expires (15 minutes after reserved_at)"
    )
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional order metadata")
    
    # Relationships (optional includes)
    items: Optional[List[OrderItemResponse]] = Field(None, description="Order items")
    status_history: Optional[List[OrderStatusHistoryResponse]] = Field(
        None, 
        description="Status change history"
    )
    stock_reservations: Optional[List[StockReservationSummary]] = Field(
        None, 
        description="Stock reservations"
    )
    
    model_config = ConfigDict(from_attributes=True)


class OrderSummary(BaseModel):
    """Summary schema for order listings."""
    
    id: UUID
    order_number: str = Field(..., description="Unique order number")
    status: OrderStatus = Field(..., description="Current order status")
    
    # Monetary amounts
    subtotal: Decimal = Field(..., ge=0, description="Subtotal")
    shipping_amount: Decimal = Field(..., ge=0, description="Shipping cost")
    tax_amount: Decimal = Field(..., ge=0, description="Tax amount")
    total: Decimal = Field(..., ge=0, description="Total amount")
    currency: str = Field(default="ARS", description="Currency code")
    
    # Timestamps
    created_at: datetime = Field(..., description="When order was created")
    updated_at: datetime = Field(..., description="When order was last updated")
    
    # Item count
    item_count: int = Field(..., ge=0, description="Number of items in order")
    
    model_config = ConfigDict(from_attributes=True)


class OrderListPaginated(BaseModel):
    """Paginated response for order listings."""
    
    orders: List[OrderSummary] = Field(default_factory=list, description="List of orders")
    total: int = Field(..., ge=0, description="Total number of orders")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=100, description="Number of items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    
    model_config = ConfigDict(from_attributes=True)


# ========== REQUEST SCHEMAS ==========

class ShippingAddressRequest(BaseModel):
    """Request schema for adding shipping address."""
    
    shipping_address: Dict[str, Any] = Field(..., description="Shipping address JSON")
    billing_address: Optional[Dict[str, Any]] = Field(
        None, 
        description="Billing address JSON (defaults to shipping_address if not provided)"
    )
    
    @field_validator("shipping_address")
    @classmethod
    def validate_shipping_address(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate shipping address has required fields."""
        required_fields = ["first_name", "last_name", "address_line1", "city", "postal_code", "country"]
        for field in required_fields:
            if field not in v or not v[field]:
                raise ValueError(f"Shipping address missing required field: {field}")
        
        # Validate country code if present
        if "country" in v and v["country"]:
            country = v["country"]
            if len(country) != 2 or not country.isalpha():
                raise ValueError("Country must be a 2-letter ISO country code")
            v["country"] = country.upper()
        
        return v
    
    @field_validator("billing_address")
    @classmethod
    def validate_billing_address(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate billing address if provided."""
        if v:
            required_fields = ["first_name", "last_name", "address_line1", "city", "postal_code", "country"]
            for field in required_fields:
                if field not in v or not v[field]:
                    raise ValueError(f"Billing address missing required field: {field}")
            
            # Validate country code if present
            if "country" in v and v["country"]:
                country = v["country"]
                if len(country) != 2 or not country.isalpha():
                    raise ValueError("Country must be a 2-letter ISO country code")
                v["country"] = country.upper()
        
        return v
    
    model_config = ConfigDict(extra='forbid')


class ShippingMethodRequest(BaseModel):
    """Request schema for selecting shipping method."""
    
    shipping_method: str = Field(..., min_length=1, max_length=50, description="Shipping method code")
    shipping_options: Optional[Dict[str, Any]] = Field(
        None, 
        description="Additional shipping options (e.g., insurance, expedited)"
    )
    
    model_config = ConfigDict(extra='forbid')


class PriceConfirmationRequest(BaseModel):
    """Request schema for confirming price changes."""
    
    confirm: bool = Field(..., description="Whether to confirm price changes")
    
    model_config = ConfigDict(extra='forbid')


# ========== VALIDATION RESPONSE ==========

class PriceChangeDetail(BaseModel):
    """Details of a price change for an order item."""
    
    order_item_id: UUID
    product_id: UUID
    variant_id: Optional[UUID]
    old_price: Decimal
    new_price: Decimal
    quantity: int
    price_difference: Decimal
    total_price_difference: Decimal
    requires_confirmation: bool = Field(default=True, description="Whether customer confirmation is required")


class OutOfStockDetail(BaseModel):
    """Details of an out-of-stock item."""
    
    product_id: UUID
    variant_id: Optional[UUID]
    quantity_requested: int
    available_qty: int
    is_backorder_allowed: bool
    product_name: Optional[str] = Field(None, description="Product name")
    variant_name: Optional[str] = Field(None, description="Variant name")


class StockValidationResponse(BaseModel):
    """Response schema for stock validation."""
    
    order_id: UUID
    order_number: str
    items_with_price_changes: List[PriceChangeDetail] = Field(default_factory=list)
    items_out_of_stock: List[OutOfStockDetail] = Field(default_factory=list)
    total_price_difference: Decimal = Field(default=0, description="Total price difference across all items")
    is_valid: bool = Field(default=True, description="Whether stock is available for all items")
    requires_price_confirmation: bool = Field(
        default=False, 
        description="Whether price changes require customer confirmation"
    )


# ========== CHECKOUT RESPONSE ==========

class CheckoutInitResponse(BaseModel):
    """Response schema for checkout initialization."""
    
    order_id: UUID = Field(..., description="Order ID")
    order_number: str = Field(..., description="Order number")
    status: OrderStatus = Field(..., description="Initial order status")
    expires_at: Optional[datetime] = Field(
        None, 
        description="When the checkout session expires (15 minutes from now)"
    )
    item_count: int = Field(..., description="Number of items in order")
    subtotal: Decimal = Field(..., description="Order subtotal")
    total: Decimal = Field(..., description="Order total")
    currency: str = Field(default="ARS", description="Currency code")
    
    model_config = ConfigDict(from_attributes=True)