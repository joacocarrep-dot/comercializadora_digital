"""
Storefront CRUD endpoints for admin users.

Provides complete CRUD operations for managing storefronts.
Generates API keys on creation (exposed only once).
Requires admin or superadmin role.
"""
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import get_current_admin_user, hash_password
from app.models.user import User
from app.repositories.storefront_repo import StorefrontRepository
from app.schemas.storefront import (
    StorefrontCreate,
    StorefrontCreateResponse,
    StorefrontListResponse,
    StorefrontResponse,
    StorefrontUpdate,
)

router = APIRouter()


def generate_api_credentials() -> tuple[str, str]:
    """
    Generate random API key and secret.
    
    Returns:
        Tuple of (api_key, api_secret) as plain text strings
    """
    api_key = secrets.token_urlsafe(32)
    api_secret = secrets.token_urlsafe(32)
    return api_key, api_secret


@router.post(
    "",
    response_model=StorefrontCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new storefront",
)
async def create_storefront(
    storefront_data: StorefrontCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Create a new storefront with generated API credentials.
    
    IMPORTANT: API key and secret are returned ONLY in this response.
    Save them immediately as they cannot be retrieved later.
    
    Requires admin or superadmin role.
    """
    storefront_repo = StorefrontRepository(db)
    
    # Check if code already exists
    existing = await storefront_repo.get_by_code(storefront_data.code)
    if existing:
        raise ConflictException(f"Storefront with code '{storefront_data.code}' already exists")
    
    # Generate API credentials
    api_key, api_secret = generate_api_credentials()
    
    # Hash credentials before storing
    api_key_hash = hash_password(api_key)
    api_secret_hash = hash_password(api_secret)
    
    # Create storefront
    storefront_dict = storefront_data.model_dump()
    storefront_dict["api_key_hash"] = api_key_hash
    storefront_dict["api_secret_hash"] = api_secret_hash
    
    storefront = await storefront_repo.create(**storefront_dict)
    
    # Return response with plain text credentials (ONLY TIME THEY ARE EXPOSED)
    response_data = StorefrontResponse.model_validate(storefront).model_dump()
    response_data["api_key"] = api_key
    response_data["api_secret"] = api_secret
    
    return StorefrontCreateResponse(**response_data)


@router.get(
    "",
    response_model=StorefrontListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all storefronts",
)
async def list_storefronts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    List all storefronts with pagination.
    
    API credentials are NOT included in the response.
    
    Requires admin or superadmin role.
    """
    storefront_repo = StorefrontRepository(db)
    
    # Get storefronts
    storefronts = await storefront_repo.get_all(skip=skip, limit=limit)
    total = await storefront_repo.count()
    
    return StorefrontListResponse(
        items=[StorefrontResponse.model_validate(s) for s in storefronts],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{storefront_id}",
    response_model=StorefrontResponse,
    status_code=status.HTTP_200_OK,
    summary="Get storefront by ID",
)
async def get_storefront(
    storefront_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get a specific storefront by ID.
    
    API credentials are NOT included in the response.
    
    Requires admin or superadmin role.
    """
    storefront_repo = StorefrontRepository(db)
    
    storefront = await storefront_repo.get_by_id(storefront_id)
    if not storefront:
        raise NotFoundException("Storefront", storefront_id)
    
    return StorefrontResponse.model_validate(storefront)


@router.put(
    "/{storefront_id}",
    response_model=StorefrontResponse,
    status_code=status.HTTP_200_OK,
    summary="Update storefront",
)
async def update_storefront(
    storefront_id: UUID,
    storefront_data: StorefrontUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Update an existing storefront.
    
    API credentials cannot be updated through this endpoint.
    
    Requires admin or superadmin role.
    """
    storefront_repo = StorefrontRepository(db)
    
    # Check if storefront exists
    existing = await storefront_repo.get_by_id(storefront_id)
    if not existing:
        raise NotFoundException("Storefront", storefront_id)
    
    # Check if code is being changed and already exists
    if storefront_data.code and storefront_data.code != existing.code:
        code_exists = await storefront_repo.get_by_code(storefront_data.code)
        if code_exists:
            raise ConflictException(f"Storefront with code '{storefront_data.code}' already exists")
    
    # Update storefront (only include non-None fields)
    update_data = storefront_data.model_dump(exclude_unset=True)
    storefront = await storefront_repo.update(storefront_id, **update_data)
    
    return StorefrontResponse.model_validate(storefront)


@router.delete(
    "/{storefront_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete storefront",
)
async def delete_storefront(
    storefront_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete a storefront.
    
    Requires admin or superadmin role.
    """
    storefront_repo = StorefrontRepository(db)
    
    # Check if storefront exists
    existing = await storefront_repo.get_by_id(storefront_id)
    if not existing:
        raise NotFoundException("Storefront", storefront_id)
    
    # Delete storefront
    await storefront_repo.delete(storefront_id)
    
    return None
