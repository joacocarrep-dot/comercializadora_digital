"""
Storefront product assignment endpoints for admin users.

Provides operations for managing product assignments to storefronts
with custom pricing, activation, and positioning per storefront.
Requires admin or superadmin role.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.core.security import get_current_admin_user
from app.models.user import User
from app.schemas.storefront_product import (
    StorefrontProductCreate,
    StorefrontProductListResponse,
    StorefrontProductResponse,
    StorefrontProductUpdate,
)
from app.repositories.base import BaseRepository
from app.models.storefront_product import StorefrontProduct
from app.models.storefront import Storefront
from app.models.product import Product

router = APIRouter()


@router.post(
    "/storefronts/{storefront_id}/products",
    response_model=StorefrontProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign product to storefront",
)
async def assign_product_to_storefront(
    storefront_id: UUID,
    product_data: StorefrontProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Assign a product to a storefront.
    
    Requires admin or superadmin role.
    Validates that storefront and product exist.
    Validates unique constraint (storefront_id, product_id).
    """
    # Validate storefront exists
    storefront_repo = BaseRepository(Storefront, db)
    storefront = await storefront_repo.get_by_id(storefront_id)
    if not storefront:
        raise NotFoundException("Storefront", storefront_id)
    
    # Validate product exists
    product_repo = BaseRepository(Product, db)
    product = await product_repo.get_by_id(product_data.product_id)
    if not product:
        raise NotFoundException("Product", product_data.product_id)
    
    # Check if assignment already exists
    storefront_product_repo = BaseRepository(StorefrontProduct, db)
    existing = await storefront_product_repo.get_all(filters={
        "storefront_id": storefront_id,
        "product_id": product_data.product_id
    })
    if existing:
        raise ConflictException(f"Product {product_data.product_id} is already assigned to storefront {storefront_id}")
    
    # Ensure storefront_id from path matches request body
    if product_data.storefront_id != storefront_id:
        raise BadRequestException("storefront_id in path does not match storefront_id in request body")
    
    # Create assignment
    assignment_dict = product_data.model_dump()
    assignment = await storefront_product_repo.create(**assignment_dict)
    
    return StorefrontProductResponse.model_validate(assignment)


@router.delete(
    "/storefronts/{storefront_id}/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unassign product from storefront",
)
async def unassign_product_from_storefront(
    storefront_id: UUID,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Unassign a product from a storefront.
    
    Requires admin or superadmin role.
    Validates that assignment exists.
    """
    # Find assignment
    storefront_product_repo = BaseRepository(StorefrontProduct, db)
    assignments = await storefront_product_repo.get_all(filters={
        "storefront_id": storefront_id,
        "product_id": product_id
    })
    
    if not assignments:
        raise NotFoundException(f"Product assignment for storefront {storefront_id} and product {product_id}")
    
    # Delete assignment
    await storefront_product_repo.delete(assignments[0].id)
    
    return None


@router.put(
    "/storefronts/{storefront_id}/products/{product_id}",
    response_model=StorefrontProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update storefront product assignment",
)
async def update_storefront_product_assignment(
    storefront_id: UUID,
    product_id: UUID,
    update_data: StorefrontProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Update a product assignment to a storefront.
    
    Requires admin or superadmin role.
    Updates custom_price, is_featured, position, and other assignment-specific fields.
    """
    # Find assignment
    storefront_product_repo = BaseRepository(StorefrontProduct, db)
    assignments = await storefront_product_repo.get_all(filters={
        "storefront_id": storefront_id,
        "product_id": product_id
    })
    
    if not assignments:
        raise NotFoundException(f"Product assignment for storefront {storefront_id} and product {product_id}")
    
    assignment = assignments[0]
    
    # Update assignment (only include non-None fields)
    update_dict = update_data.model_dump(exclude_unset=True)
    updated_assignment = await storefront_product_repo.update(assignment.id, **update_dict)
    
    return StorefrontProductResponse.model_validate(updated_assignment)


@router.get(
    "/storefront-products",
    response_model=StorefrontProductListResponse,
    status_code=status.HTTP_200_OK,
    summary="List storefront product assignments with filtering",
)
async def list_storefront_products(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    storefront_id: Optional[UUID] = Query(None, description="Filter by storefront ID"),
    product_id: Optional[UUID] = Query(None, description="Filter by product ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_featured: Optional[bool] = Query(None, description="Filter by featured status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    List storefront product assignments with pagination and filtering.
    
    Requires admin or superadmin role.
    Supports filtering by storefront, product, active status, and featured status.
    """
    storefront_product_repo = BaseRepository(StorefrontProduct, db)
    
    # Build filters
    filters = {}
    if storefront_id:
        filters["storefront_id"] = storefront_id
    if product_id:
        filters["product_id"] = product_id
    if is_active is not None:
        filters["is_active"] = is_active
    if is_featured is not None:
        filters["is_featured"] = is_featured
    
    # Get assignments
    assignments = await storefront_product_repo.get_all(skip=skip, limit=limit, filters=filters)
    total = await storefront_product_repo.count(filters=filters)
    
    # Calculate pagination
    page = (skip // limit) + 1 if limit > 0 else 1
    per_page = limit
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    
    return StorefrontProductListResponse(
        items=[StorefrontProductResponse.model_validate(a) for a in assignments],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get(
    "/storefront-products/{assignment_id}",
    response_model=StorefrontProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get storefront product assignment by ID",
)
async def get_storefront_product_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get a specific storefront product assignment by ID.
    
    Requires admin or superadmin role.
    """
    storefront_product_repo = BaseRepository(StorefrontProduct, db)
    assignment = await storefront_product_repo.get_by_id(assignment_id)
    
    if not assignment:
        raise NotFoundException("StorefrontProduct", assignment_id)
    
    return StorefrontProductResponse.model_validate(assignment)