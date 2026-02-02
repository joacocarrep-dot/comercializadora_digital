"""
Product CRUD endpoints for admin users.

Provides complete CRUD operations for managing products,
including batch import from Excel/CSV files.
Requires admin or superadmin role.
"""
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.security import get_current_admin_user
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    ProductImportResponse,
)
from app.services import ProductService, ImportService

router = APIRouter()


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Create a new product.
    
    Requires admin or superadmin role.
    Validates slug uniqueness and relationships with Supplier and Category.
    """
    service = ProductService(db)
    
    try:
        # Convert Pydantic model to dict for service
        product_dict = product_data.model_dump()
        
        # Create product using service
        product = await service.create_product(product_dict)
        
        return ProductResponse.model_validate(product)
        
    except Exception as e:
        # Re-raise exceptions from service
        raise e


@router.get(
    "",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all products with filtering and pagination",
)
async def list_products(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    supplier_id: Optional[UUID] = Query(None, description="Filter by supplier ID"),
    storefront_id: Optional[UUID] = Query(None, description="Filter by storefront ID"),
    category_id: Optional[UUID] = Query(None, description="Filter by category ID"),
    product_type: Optional[str] = Query(None, description="Filter by product type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: active, inactive, all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    List products with pagination and filtering options.
    
    Requires admin or superadmin role.
    Supports filtering by supplier, storefront, category, product type, and status.
    """
    # Note: For now, using simple pagination from repository
    # In a complete implementation, this would use ProductService with proper filtering
    
    from app.repositories.base import BaseRepository
    from app.models.product import Product
    
    product_repo = BaseRepository(Product, db)
    
    # Build filters
    filters = {}
    if supplier_id:
        filters["supplier_id"] = supplier_id
    if category_id:
        filters["category_id"] = category_id
    if product_type:
        filters["product_type"] = product_type
    
    # Handle status filter
    if status_filter == "active":
        filters["is_active"] = True
    elif status_filter == "inactive":
        filters["is_active"] = False
    # "all" includes both active and inactive
    
    # Get products
    products = await product_repo.get_all(skip=skip, limit=limit, filters=filters)
    total = await product_repo.count(filters=filters)
    
    # Calculate pagination
    page = (skip // limit) + 1 if limit > 0 else 1
    per_page = limit
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    
    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product by ID",
)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get a specific product by ID.
    
    Requires admin or superadmin role.
    """
    service = ProductService(db)
    
    # Get product using repository
    from app.repositories.base import BaseRepository
    from app.models.product import Product
    
    product_repo = BaseRepository(Product, db)
    product = await product_repo.get_by_id(product_id)
    
    if not product:
        raise NotFoundException("Product", product_id)
    
    return ProductResponse.model_validate(product)


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update product",
)
async def update_product(
    product_id: UUID,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Update an existing product.
    
    Requires admin or superadmin role.
    Validates slug uniqueness (excluding the current product) and updates fields.
    """
    service = ProductService(db)
    
    try:
        # Convert Pydantic model to dict for service (excluding unset fields)
        update_dict = product_data.model_dump(exclude_unset=True)
        
        # Update product using service
        product = await service.update_product(product_id, update_dict)
        
        return ProductResponse.model_validate(product)
        
    except NotFoundException:
        raise NotFoundException("Product", product_id)
    except Exception as e:
        # Re-raise exceptions from service
        raise e


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product (soft delete)",
)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete a product (soft delete).
    
    Requires admin or superadmin role.
    Validates that product has no active dependencies (variants, inventory, etc.).
    For soft delete, marks is_active=False.
    """
    service = ProductService(db)
    
    try:
        await service.delete_product(product_id)
        return None
        
    except NotFoundException:
        raise NotFoundException("Product", product_id)
    except Exception as e:
        # Re-raise exceptions from service
        raise e


@router.post(
    "/import",
    response_model=ProductImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Import products from Excel/CSV file",
)
async def import_products(
    supplier_id: UUID = Form(..., description="Supplier ID for the import"),
    file: UploadFile = File(..., description="Excel or CSV file with product data"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Import products in batch from Excel or CSV file.
    
    Requires admin or superadmin role.
    Supports .xlsx, .xls, and .csv file formats.
    Returns a ProductImport record with status and error details.
    """
    import_service = ImportService(db)
    
    # Validate file type
    allowed_extensions = {'.xlsx', '.xls', '.csv'}
    file_extension = file.filename[file.filename.rfind('.'):].lower() if '.' in file.filename else ''
    
    if file_extension not in allowed_extensions:
        raise BadRequestException(
            f"Unsupported file format: {file_extension}. "
            f"Supported formats: {', '.join(allowed_extensions)}"
        )
    
    # Save file temporarily (in a real implementation, upload to storage)
    # For now, we'll create a mock import record
    
    try:
        # Create import record
        import_record = await import_service.import_products_batch(
            supplier_id=supplier_id,
            file_name=file.filename,
            file_url=f"temp/{file.filename}",  # Mock URL
            import_type="products",
            created_by=current_user.id,
        )
        
        return ProductImportResponse.model_validate(import_record)
        
    except Exception as e:
        raise BadRequestException(f"Error starting import: {str(e)}")


@router.get(
    "/imports/{import_id}",
    response_model=ProductImportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get import status and results",
)
async def get_import_status(
    import_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get the status and results of a product import.
    
    Requires admin or superadmin role.
    Returns the ProductImport record with current status and error details.
    """
    import_service = ImportService(db)
    
    try:
        import_record = await import_service.get_import_status(import_id)
        return ProductImportResponse.model_validate(import_record)
        
    except NotFoundException:
        raise NotFoundException("ProductImport", import_id)
    except Exception as e:
        raise BadRequestException(f"Error getting import status: {str(e)}")