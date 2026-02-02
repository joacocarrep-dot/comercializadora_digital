"""
Import service for batch product import from Excel/CSV files.

Handles file parsing, validation, and bulk product creation/update.
Supports Excel (.xlsx, .xls) and CSV file formats.
"""
import asyncio
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException
from app.models.product import Product, ProductType
from app.models.product_import import ProductImport
from app.models.supplier import Supplier
from app.repositories.base import BaseRepository
from app.schemas.product import ProductCreate


class ImportService:
    """
    Service for batch product import operations.
    
    Attributes:
        session: Async database session
        product_repo: BaseRepository for Product model
        product_import_repo: BaseRepository for ProductImport model
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize import service with database session.
        
        Args:
            session: Async database session
        """
        self.session = session
        self.product_repo = BaseRepository(Product, session)
        self.product_import_repo = BaseRepository(ProductImport, session)
    
    async def parse_excel_csv(
        self,
        file_path: str,
        file_extension: str,
        supplier_id: UUID
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Parse Excel or CSV file and extract product data.
        
        Args:
            file_path: Path to the uploaded file
            file_extension: File extension (.xlsx, .xls, .csv)
            supplier_id: ID of supplier for this import
            
        Returns:
            Tuple of (list of parsed rows, list of parsing errors)
            
        Raises:
            BadRequestException: If file format is unsupported or file is empty
        """
        try:
            # Read file based on extension
            if file_extension.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, dtype=str)
            elif file_extension.lower() == '.csv':
                df = pd.read_csv(file_path, dtype=str)
            else:
                raise BadRequestException(
                    f"Unsupported file format: {file_extension}. "
                    "Supported formats: .xlsx, .xls, .csv"
                )
            
            # Check if file is empty
            if df.empty:
                raise BadRequestException("File is empty")
            
            # Replace NaN with None
            df = df.where(pd.notnull(df), None)
            
            # Convert to list of dictionaries
            rows = df.to_dict('records')
            
            # Basic validation and error collection
            errors = []
            valid_rows = []
            
            for i, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
                row_errors = []
                
                # Check required fields
                if not row.get('name'):
                    row_errors.append({"field": "name", "error": "Name is required"})
                
                if not row.get('sku'):
                    row_errors.append({"field": "sku", "error": "SKU is required"})
                
                # Validate price fields
                if row.get('base_price'):
                    try:
                        Decimal(str(row['base_price']))
                    except:
                        row_errors.append({"field": "base_price", "error": "Invalid price format"})
                
                if row_errors:
                    errors.append({
                        "row": i,
                        "row_data": row,
                        "errors": row_errors
                    })
                else:
                    # Add supplier_id to each row
                    row['supplier_id'] = str(supplier_id)
                    valid_rows.append(row)
            
            return valid_rows, errors
            
        except pd.errors.EmptyDataError:
            raise BadRequestException("File is empty or contains no data")
        except Exception as e:
            raise BadRequestException(f"Error parsing file: {str(e)}")
    
    async def validate_batch(
        self,
        rows: List[Dict[str, Any]],
        supplier_id: UUID
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate batch of product data using Pydantic schemas.
        
        Args:
            rows: List of parsed product data
            supplier_id: ID of supplier for validation
            
        Returns:
            Tuple of (list of valid product data, list of validation errors)
        """
        from app.schemas.product import ProductCreate
        
        valid_data = []
        errors = []
        
        # Verify supplier exists
        supplier = await self.session.get(Supplier, supplier_id)
        if not supplier:
            raise BadRequestException(f"Supplier not found: {supplier_id}")
        
        for i, row in enumerate(rows, start=2):  # Start at 2 (accounting for header)
            try:
                # Convert string values to appropriate types
                processed_row = self._preprocess_row(row)
                
                # Validate with Pydantic schema
                product_data = ProductCreate(**processed_row)
                
                # Convert to dict for database operations
                valid_data.append(product_data.model_dump())
                
            except Exception as e:
                # Extract field-specific errors if available
                if hasattr(e, 'errors'):
                    error_details = [
                        {"field": err['loc'][0], "error": err['msg']}
                        for err in e.errors()
                    ]
                else:
                    error_details = [{"field": "general", "error": str(e)}]
                
                errors.append({
                    "row": i,
                    "row_data": row,
                    "errors": error_details
                })
        
        return valid_data, errors
    
    async def import_products_batch(
        self,
        supplier_id: UUID,
        file_name: str,
        file_url: str,
        import_type: str = "products",
        created_by: Optional[UUID] = None,
        max_rows: int = 1000,
        timeout_seconds: int = 60
    ) -> ProductImport:
        """
        Import products in batch with transaction and timeout.
        
        Args:
            supplier_id: ID of supplier
            file_name: Original file name
            file_url: File storage URL
            import_type: Type of import (default: "products")
            created_by: User ID who initiated the import
            max_rows: Maximum number of rows to process (default: 1000)
            timeout_seconds: Timeout for the import operation (default: 60)
            
        Returns:
            ProductImport record with import status and results
            
        Raises:
            BadRequestException: If batch exceeds max_rows or timeout occurs
        """
        # This method is a placeholder for the full implementation
        # In a real implementation, this would:
        # 1. Create ProductImport record with status "processing"
        # 2. Parse and validate the file
        # 3. Import products in a transaction
        # 4. Update ProductImport record with results
        
        # For now, create a basic ProductImport record
        import_data = {
            "supplier_id": supplier_id,
            "import_type": import_type,
            "file_name": file_name,
            "file_url": file_url,
            "status": "pending",
            "total_rows": 0,
            "processed_rows": 0,
            "success_count": 0,
            "error_count": 0,
            "errors": [],
            "created_by": created_by,
            "started_at": datetime.utcnow(),
        }
        
        product_import = await self.product_import_repo.create(**import_data)
        
        # Note: Actual import logic would go here
        # This would involve calling parse_excel_csv, validate_batch,
        # and creating/updating products in a transaction
        
        return product_import
    
    async def get_import_status(self, import_id: UUID) -> ProductImport:
        """
        Get the status and results of a product import.
        
        Args:
            import_id: ID of the ProductImport record
            
        Returns:
            ProductImport record with current status and results
            
        Raises:
            NotFoundException: If import record not found
        """
        product_import = await self.product_import_repo.get_by_id(import_id)
        if not product_import:
            from app.core.exceptions import NotFoundException
            raise NotFoundException("ProductImport", import_id)
        
        return product_import
    
    def _preprocess_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess row data for validation.
        
        Args:
            row: Raw row data from file
            
        Returns:
            Processed row data with proper types
        """
        processed = row.copy()
        
        # Handle price fields
        price_fields = ['base_price', 'compare_price', 'cost_price']
        for field in price_fields:
            if field in processed and processed[field] is not None:
                try:
                    # Remove currency symbols and format as string for Decimal
                    value = str(processed[field]).replace('$', '').replace(',', '').strip()
                    processed[field] = value
                except:
                    pass  # Will be caught by validation
        
        # Handle numeric fields
        numeric_fields = ['tax_rate']
        for field in numeric_fields:
            if field in processed and processed[field] is not None:
                try:
                    processed[field] = float(processed[field])
                except:
                    pass
        
        # Handle boolean fields
        boolean_fields = ['is_active', 'is_featured']
        for field in boolean_fields:
            if field in processed and processed[field] is not None:
                value = str(processed[field]).lower()
                processed[field] = value in ['true', 'yes', '1', 'on']
        
        # Handle JSON fields
        if 'attributes' in processed and processed['attributes'] is not None:
            if isinstance(processed['attributes'], str):
                # Try to parse as JSON string
                import json
                try:
                    processed['attributes'] = json.loads(processed['attributes'])
                except:
                    processed['attributes'] = {}
        
        if 'images' in processed and processed['images'] is not None:
            if isinstance(processed['images'], str):
                import json
                try:
                    processed['images'] = json.loads(processed['images'])
                except:
                    processed['images'] = []
        
        # Ensure required string fields
        string_fields = ['name', 'slug', 'sku', 'product_type', 'currency']
        for field in string_fields:
            if field in processed and processed[field] is not None:
                processed[field] = str(processed[field])
        
        return processed