"""
Pydantic schemas for Supplier endpoints.

Defines request/response models for supplier CRUD operations.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SupplierBase(BaseModel):
    """Base schema with common supplier fields."""
    
    code: str = Field(..., min_length=1, max_length=50, description="Unique supplier code")
    name: str = Field(..., min_length=1, max_length=255, description="Supplier name")
    legal_name: Optional[str] = Field(None, max_length=255, description="Legal business name")
    tax_id: Optional[str] = Field(None, max_length=50, description="Tax identification number")
    contact_name: Optional[str] = Field(None, max_length=255, description="Contact person name")
    contact_email: Optional[str] = Field(None, max_length=255, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Contact phone")
    api_config: Optional[dict] = Field(default_factory=dict, description="API integration config")
    sync_config: Optional[dict] = Field(default_factory=dict, description="Sync settings")
    export_config: Optional[dict] = Field(default_factory=dict, description="Export settings")
    is_active: bool = Field(default=True, description="Whether supplier is active")


class SupplierCreate(SupplierBase):
    """Schema for creating a new supplier."""
    pass


class SupplierUpdate(BaseModel):
    """Schema for updating an existing supplier (all fields optional)."""
    
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    legal_name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    api_config: Optional[dict] = None
    sync_config: Optional[dict] = None
    export_config: Optional[dict] = None
    is_active: Optional[bool] = None


class SupplierResponse(SupplierBase):
    """Schema for supplier response."""
    
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SupplierListResponse(BaseModel):
    """Schema for paginated supplier list response."""
    
    items: list[SupplierResponse]
    total: int
    skip: int
    limit: int
