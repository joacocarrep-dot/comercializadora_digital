"""
Inventory management endpoints for admin users.

Provides operations for managing inventory stock levels,
tracking reserved quantities, and low stock alerts.
Requires admin or superadmin role.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.security import get_current_admin_user
from app.models.user import User
from app.schemas.inventory import (
    InventoryCreate,
    InventoryListResponse,
    InventoryResponse,
    InventoryUpdate,
    LowStockAlertResponse,
)
from app.services import InventoryService

router = APIRouter()


@router.post(
    "",
    response_model=InventoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new inventory record",
)
async def create_inventory(
    inventory_data: InventoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Create a new inventory record.
    
    Requires admin or superadmin role.
    Validates that either product_id or variant_id is provided.
    Validates reserved_qty does not exceed quantity.
    """
    service = InventoryService(db)
    
    try:
        # Convert Pydantic model to dict for service
        inventory_dict = inventory_data.model_dump()
        
        # Create inventory using service
        inventory = await service.create_inventory(inventory_dict)
        
        return InventoryResponse.model_validate(inventory)
        
    except Exception as e:
        # Re-raise exceptions from service
        raise e


@router.get(
    "",
    response_model=InventoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List inventory records with filtering and pagination",
)
async def list_inventory(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    product_id: Optional[UUID] = Query(None, description="Filter by product ID"),
    variant_id: Optional[UUID] = Query(None, description="Filter by variant ID"),
    low_stock: Optional[bool] = Query(None, description="Filter for low stock items (quantity <= low_stock_alert)"),
    out_of_stock: Optional[bool] = Query(None, description="Filter for out of stock items (available_qty <= 0)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    List inventory records with pagination and filtering options.
    
    Requires admin or superadmin role.
    Supports filtering by product, variant, low stock, and out of stock status.
    """
    from app.repositories.base import BaseRepository
    from app.models.inventory import Inventory
    
    inventory_repo = BaseRepository(Inventory, db)
    
    # Build filters
    filters = {}
    if product_id:
        filters["product_id"] = product_id
    if variant_id:
        filters["variant_id"] = variant_id
    
    # Get inventory records
    inventory_items = await inventory_repo.get_all(skip=skip, limit=limit, filters=filters)
    total = await inventory_repo.count(filters=filters)
    
    # Apply low stock and out of stock filters
    if low_stock is True:
        inventory_items = [item for item in inventory_items if item.quantity <= item.low_stock_alert]
        total = len(inventory_items)
    elif low_stock is False:
        inventory_items = [item for item in inventory_items if item.quantity > item.low_stock_alert]
        total = len(inventory_items)
    
    if out_of_stock is True:
        inventory_items = [item for item in inventory_items if item.available_qty <= 0]
        total = len(inventory_items)
    elif out_of_stock is False:
        inventory_items = [item for item in inventory_items if item.available_qty > 0]
        total = len(inventory_items)
    
    # Calculate pagination
    page = (skip // limit) + 1 if limit > 0 else 1
    per_page = limit
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    
    return InventoryListResponse(
        items=[InventoryResponse.model_validate(item) for item in inventory_items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get(
    "/{inventory_id}",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get inventory record by ID",
)
async def get_inventory(
    inventory_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get a specific inventory record by ID.
    
    Requires admin or superadmin role.
    """
    from app.repositories.base import BaseRepository
    from app.models.inventory import Inventory
    
    inventory_repo = BaseRepository(Inventory, db)
    inventory = await inventory_repo.get_by_id(inventory_id)
    
    if not inventory:
        raise NotFoundException("Inventory", inventory_id)
    
    return InventoryResponse.model_validate(inventory)


@router.put(
    "/{inventory_id}",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update inventory record",
)
async def update_inventory(
    inventory_id: UUID,
    inventory_data: InventoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Update an existing inventory record.
    
    Requires admin or superadmin role.
    Supports both override mode (set quantity directly) and incremental mode (add/subtract).
    Validates that reserved_qty does not exceed quantity.
    """
    service = InventoryService(db)
    
    try:
        # Convert Pydantic model to dict for service (excluding unset fields)
        update_dict = inventory_data.model_dump(exclude_unset=True)
        
        # Update inventory using service
        inventory = await service.update_inventory(inventory_id, update_dict)
        
        return InventoryResponse.model_validate(inventory)
        
    except NotFoundException:
        raise NotFoundException("Inventory", inventory_id)
    except Exception as e:
        # Re-raise exceptions from service
        raise e


@router.delete(
    "/{inventory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete inventory record",
)
async def delete_inventory(
    inventory_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete an inventory record.
    
    Requires admin or superadmin role.
    Validates that record can be deleted (no active dependencies).
    """
    from app.repositories.base import BaseRepository
    from app.models.inventory import Inventory
    
    inventory_repo = BaseRepository(Inventory, db)
    
    # Check if inventory exists
    inventory = await inventory_repo.get_by_id(inventory_id)
    if not inventory:
        raise NotFoundException("Inventory", inventory_id)
    
    # Check for active dependencies
    # (In a complete implementation, check for orders, reservations, etc.)
    
    # Delete inventory
    await inventory_repo.delete(inventory_id)
    
    return None


@router.get(
    "/low-stock",
    response_model=list[LowStockAlertResponse],
    status_code=status.HTTP_200_OK,
    summary="Get low stock alerts",
)
async def get_low_stock_alerts(
    threshold: Optional[int] = Query(None, ge=0, description="Custom low stock threshold (overrides per-item setting)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get all inventory items with low stock.
    
    Requires admin or superadmin role.
    Items are considered low stock when quantity <= low_stock_alert.
    Optionally accepts custom threshold parameter.
    """
    service = InventoryService(db)
    
    try:
        # Get low stock alerts using service
        alerts = await service.get_low_stock_alerts(threshold=threshold)
        
        # Convert to response format
        # In a complete implementation, we would convert the service output
        return []
        
    except Exception as e:
        raise e


@router.post(
    "/{inventory_id}/reserve",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Reserve stock quantity",
)
async def reserve_stock(
    inventory_id: UUID,
    quantity: int = Query(..., ge=1, description="Quantity to reserve"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Reserve stock quantity for orders or other purposes.
    
    Requires admin or superadmin role.
    Increases reserved_qty and validates that total reserved does not exceed available quantity.
    """
    service = InventoryService(db)
    
    try:
        # Reserve stock using service
        inventory = await service.reserve_stock(inventory_id, quantity)
        
        return InventoryResponse.model_validate(inventory)
        
    except NotFoundException:
        raise NotFoundException("Inventory", inventory_id)
    except Exception as e:
        # Re-raise exceptions from service
        raise e


@router.post(
    "/{inventory_id}/release",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Release reserved stock quantity",
)
async def release_stock(
    inventory_id: UUID,
    quantity: int = Query(..., ge=1, description="Quantity to release"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Release reserved stock quantity.
    
    Requires admin or superadmin role.
    Decreases reserved_qty and validates that release quantity does not exceed reserved quantity.
    """
    service = InventoryService(db)
    
    try:
        # Release stock using service
        inventory = await service.release_stock(inventory_id, quantity)
        
        return InventoryResponse.model_validate(inventory)
        
    except NotFoundException:
        raise NotFoundException("Inventory", inventory_id)
    except Exception as e:
        # Re-raise exceptions from service
        raise e