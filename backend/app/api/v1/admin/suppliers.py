"""
Supplier CRUD endpoints for admin users.

Provides complete CRUD operations for managing suppliers.
Requires admin or superadmin role.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import get_current_admin_user
from app.models.user import User
from app.repositories.supplier_repo import SupplierRepository
from app.schemas.supplier import (
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)

router = APIRouter()


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new supplier",
)
async def create_supplier(
    supplier_data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Create a new supplier.
    
    Requires admin or superadmin role.
    """
    supplier_repo = SupplierRepository(db)
    
    # Check if code already exists
    existing = await supplier_repo.get_by_code(supplier_data.code)
    if existing:
        raise ConflictException(f"Supplier with code '{supplier_data.code}' already exists")
    
    # Create supplier
    supplier = await supplier_repo.create(**supplier_data.model_dump())
    
    return SupplierResponse.model_validate(supplier)


@router.get(
    "",
    response_model=SupplierListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all suppliers",
)
async def list_suppliers(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    List all suppliers with pagination.
    
    Requires admin or superadmin role.
    """
    supplier_repo = SupplierRepository(db)
    
    # Get suppliers
    suppliers = await supplier_repo.get_all(skip=skip, limit=limit)
    total = await supplier_repo.count()
    
    return SupplierListResponse(
        items=[SupplierResponse.model_validate(s) for s in suppliers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Get supplier by ID",
)
async def get_supplier(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get a specific supplier by ID.
    
    Requires admin or superadmin role.
    """
    supplier_repo = SupplierRepository(db)
    
    supplier = await supplier_repo.get_by_id(supplier_id)
    if not supplier:
        raise NotFoundException("Supplier", supplier_id)
    
    return SupplierResponse.model_validate(supplier)


@router.put(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Update supplier",
)
async def update_supplier(
    supplier_id: UUID,
    supplier_data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Update an existing supplier.
    
    Requires admin or superadmin role.
    """
    supplier_repo = SupplierRepository(db)
    
    # Check if supplier exists
    existing = await supplier_repo.get_by_id(supplier_id)
    if not existing:
        raise NotFoundException("Supplier", supplier_id)
    
    # Check if code is being changed and already exists
    if supplier_data.code and supplier_data.code != existing.code:
        code_exists = await supplier_repo.get_by_code(supplier_data.code)
        if code_exists:
            raise ConflictException(f"Supplier with code '{supplier_data.code}' already exists")
    
    # Update supplier (only include non-None fields)
    update_data = supplier_data.model_dump(exclude_unset=True)
    supplier = await supplier_repo.update(supplier_id, **update_data)
    
    return SupplierResponse.model_validate(supplier)


@router.delete(
    "/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete supplier",
)
async def delete_supplier(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete a supplier.
    
    Requires admin or superadmin role.
    """
    supplier_repo = SupplierRepository(db)
    
    # Check if supplier exists
    existing = await supplier_repo.get_by_id(supplier_id)
    if not existing:
        raise NotFoundException("Supplier", supplier_id)
    
    # Delete supplier
    await supplier_repo.delete(supplier_id)
    
    return None
