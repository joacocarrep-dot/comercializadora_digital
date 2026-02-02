"""
Supplier model for managing product suppliers.

Stores supplier information including contact details and configuration
for API integration, synchronization, and export settings.
"""
from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Supplier(Base, UUIDMixin, TimestampMixin):
    """
    Supplier entity representing a product supplier.
    
    Attributes:
        code: Unique identifier code for the supplier
        name: Display name of the supplier
        legal_name: Legal business name
        tax_id: Tax identification number
        contact_name: Primary contact person name
        contact_email: Primary contact email
        contact_phone: Primary contact phone number
        api_config: JSON configuration for API integration
        sync_config: JSON configuration for synchronization settings
        export_config: JSON configuration for export settings
        is_active: Whether the supplier is currently active
    """
    
    __tablename__ = "suppliers"
    
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    legal_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    tax_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    contact_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    contact_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    api_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    
    sync_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    
    export_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    # Relationships
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="supplier",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    product_imports: Mapped[list["ProductImport"]] = relationship(
        "ProductImport",
        back_populates="supplier",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<Supplier(id={self.id}, code={self.code}, name={self.name})>"
