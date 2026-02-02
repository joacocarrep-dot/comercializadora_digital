"""
ProductImport model for tracking batch import operations.

Records import jobs for products from Excel/CSV files with
status tracking and error reporting.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ProductImport(Base, UUIDMixin, TimestampMixin):
    """
    Product import entity representing a batch import operation.
    
    Attributes:
        supplier_id: Foreign key to supplier
        import_type: Type of import (products, variants, etc.)
        file_name: Original uploaded file name
        file_url: File storage URL
        status: Import status (pending, processing, completed, failed)
        total_rows: Total number of rows in the file
        processed_rows: Number of rows processed
        success_count: Number of successful imports
        error_count: Number of rows with errors
        errors: JSONB array of error details
        created_by: User who initiated the import
        started_at: When import processing started
        completed_at: When import processing completed
    """
    
    __tablename__ = "product_imports"
    
    # Foreign keys
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    import_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    file_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )
    
    total_rows: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    processed_rows: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    success_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    error_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    errors: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )
    
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    
    started_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )
    
    # Relationships
    supplier: Mapped["Supplier"] = relationship(
        "Supplier",
        back_populates="product_imports",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<ProductImport(id={self.id}, file={self.file_name}, status={self.status}, success={self.success_count}, errors={self.error_count})>"