"""
Storefront model for managing multi-tenant storefronts.

Each storefront represents an independent e-commerce site with its own
API credentials, configuration, and payment/AI settings.
"""
from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Storefront(Base, UUIDMixin, TimestampMixin):
    """
    Storefront entity representing an independent e-commerce site.
    
    Attributes:
        code: Unique identifier code for the storefront
        name: Display name of the storefront
        domain: Domain name for the storefront
        api_key_hash: Bcrypt hash of the API key for authentication
        api_secret_hash: Bcrypt hash of the API secret
        config: JSON configuration for general storefront settings
        base_currency: Base currency code (default: ARS)
        payment_config: JSON configuration for payment gateway settings
        ai_config: JSON configuration for AI assistant settings
        is_active: Whether the storefront is currently active
    """
    
    __tablename__ = "storefronts"
    
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
    
    domain: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    api_key_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    
    api_secret_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    
    base_currency: Mapped[str] = mapped_column(
        String(3),
        default="ARS",
        nullable=False,
    )
    
    payment_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    
    ai_config: Mapped[Optional[dict]] = mapped_column(
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
    storefront_products: Mapped[list["StorefrontProduct"]] = relationship(
        "StorefrontProduct",
        back_populates="storefront",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<Storefront(id={self.id}, code={self.code}, name={self.name})>"
