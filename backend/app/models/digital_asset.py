"""
DigitalAsset model for managing digital product assets.

Stores digital files associated with products, such as downloadable
content, preview images, or documentation.
"""
import uuid
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class DigitalAsset(Base, UUIDMixin, TimestampMixin):
    """
    DigitalAsset entity representing a digital file associated with a product.
    
    Attributes:
        product_id: Foreign key to product
        file_name: Original file name
        file_url: Absolute URL to access the file
        file_type: MIME type or file extension
        file_size_bytes: File size in bytes
        is_preview: Whether this asset is a preview
        position: Position for ordering assets
    """
    
    __tablename__ = "digital_assets"
    
    # Foreign key
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    file_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    
    file_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    
    is_preview: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    position: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        index=True,
    )
    
    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="digital_assets",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<DigitalAsset(id={self.id}, file_name={self.file_name}, product_id={self.product_id}, is_preview={self.is_preview})>"