"""
Public cart endpoints for storefronts.

Provides shopping cart functionality for both authenticated users
and anonymous guests. Supports adding, updating, removing items,
and clearing the cart. Uses X-API-Key for storefront identification,
JWT for user authentication (optional), and X-Anonymous-ID for guest users.
"""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_cart_service,
    get_current_storefront,
    get_current_user_optional,
    get_db,
)
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.models.storefront import Storefront
from app.models.user import User
from app.schemas.cart import (
    AddItemRequest,
    CartIdentificationHeaders,
    CartResponse,
    UpdateItemRequest,
)
from app.services import CartService

router = APIRouter()


@router.get(
    "",
    response_model=CartResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current cart",
)
async def get_cart(
    request: Request,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
    db: AsyncSession = Depends(get_db),
    cart_service: CartService = Depends(get_cart_service),
) -> CartResponse:
    """
    Get the current shopping cart.
    
    Identifies cart by:
    - user_id (if authenticated via JWT) OR
    - anonymous_id (if provided in X-Anonymous-ID header)
    
    If neither is provided, returns a BadRequestException.
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    - X-Anonymous-ID: Optional anonymous identifier for guest users
    
    Returns cart with items, current prices, and subtotal.
    """
    if not current_user and not x_anonymous_id:
        raise BadRequestException(
            "Either authentication (JWT) or X-Anonymous-ID header is required to identify cart"
        )
    
    user_id = current_user.id if current_user else None
    anonymous_id = x_anonymous_id
    
    # Get or create cart
    cart = await cart_service.get_or_create_cart(
        storefront_id=storefront.id,
        user_id=user_id,
        anonymous_id=anonymous_id,
    )
    
    # Get cart with items
    cart_with_items = await cart_service.cart_repo.get_cart_with_items(cart.id)
    if not cart_with_items:
        raise NotFoundException("Cart", cart.id)
    
    # Validate cart to detect price changes
    validation = await cart_service.validate_cart(cart.id)
    
    # Prepare response items
    items = []
    subtotal = Decimal("0.00")
    
    for item in cart_with_items.cart_items:
        # Get current price for this product/variant
        current_price = await cart_service._get_current_product_price(
            item.product_id, item.variant_id, cart.storefront_id
        )
        
        # Check if price has changed
        price_changed = current_price != item.price_at_addition
        
        # Get product details
        product = await cart_service.product_repo.get_by_id(item.product_id)
        if not product:
            # Product may have been deleted - skip or handle gracefully
            continue
        
        # Check if product is still active and assigned to storefront
        storefront_product = await cart_service._get_storefront_product_assignment(
            cart.storefront_id, item.product_id
        )
        
        product_active = (
            product.is_active and 
            storefront_product is not None and 
            storefront_product.is_active
        )
        
        # Get product image from images JSONB field
        image_url = None
        if product.images and isinstance(product.images, list):
            for img_data in product.images:
                if isinstance(img_data, dict) and "url" in img_data:
                    image_url = img_data.get("url")
                    break
        
        # Get variant details if applicable
        variant = None
        if item.variant_id:
            variant_obj = await cart_service.product_variant_repo.get_by_id(item.variant_id)
            if variant_obj:
                variant = {
                    "id": variant_obj.id,
                    "name": variant_obj.name,
                    "sku": variant_obj.sku,
                }
        
        item_total = current_price * item.quantity
        subtotal += item_total
        
        items.append({
            "id": item.id,
            "product": {
                "id": product.id,
                "name": product.name,
                "slug": product.slug,
                "image_url": image_url,
            },
            "variant": variant,
            "quantity": item.quantity,
            "unit_price": current_price,
            "total_price": item_total,
            "price_changed": price_changed,
            "product_active": product_active,
            "added_at": item.added_at.isoformat(),
        })
    
    return CartResponse(
        id=cart.id,
        items=items,
        subtotal=subtotal,
        currency="ARS",  # Assuming ARS as default currency
        item_count=len(cart_with_items.cart_items),
        storefront_id=storefront.id,
        user_id=user_id,
        anonymous_id=anonymous_id,
    )


@router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to cart",
)
async def add_item_to_cart(
    request: AddItemRequest,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
    db: AsyncSession = Depends(get_db),
    cart_service: CartService = Depends(get_cart_service),
) -> CartResponse:
    """
    Add an item to the cart or increment quantity if already exists.
    
    Validates:
    - Product exists and is active
    - Product is assigned to the current storefront
    - Variant belongs to the product (if provided)
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    - X-Anonymous-ID: Optional anonymous identifier for guest users
    
    Returns updated cart after adding item.
    """
    if not current_user and not x_anonymous_id:
        raise BadRequestException(
            "Either authentication (JWT) or X-Anonymous-ID header is required to identify cart"
        )
    
    user_id = current_user.id if current_user else None
    anonymous_id = x_anonymous_id
    
    # Get or create cart
    cart = await cart_service.get_or_create_cart(
        storefront_id=storefront.id,
        user_id=user_id,
        anonymous_id=anonymous_id,
    )
    
    # Add item to cart
    cart_item = await cart_service.add_item(
        cart_id=cart.id,
        product_id=request.product_id,
        quantity=request.quantity,
        variant_id=request.variant_id,
    )
    
    # Return updated cart
    return await get_cart(
        request=request,
        storefront=storefront,
        current_user=current_user,
        x_anonymous_id=anonymous_id,
        db=db,
        cart_service=cart_service,
    )


@router.patch(
    "/items/{item_id}",
    response_model=CartResponse,
    status_code=status.HTTP_200_OK,
    summary="Update cart item quantity",
)
async def update_cart_item_quantity(
    item_id: UUID,
    request: UpdateItemRequest,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
    db: AsyncSession = Depends(get_db),
    cart_service: CartService = Depends(get_cart_service),
) -> CartResponse:
    """
    Update quantity of a cart item.
    
    Validates:
    - Item exists and belongs to the user's/anonymous cart
    - Quantity is positive (> 0)
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    - X-Anonymous-ID: Optional anonymous identifier for guest users
    
    Returns updated cart after modifying quantity.
    """
    if not current_user and not x_anonymous_id:
        raise BadRequestException(
            "Either authentication (JWT) or X-Anonymous-ID header is required to identify cart"
        )
    
    user_id = current_user.id if current_user else None
    anonymous_id = x_anonymous_id
    
    # Get or create cart
    cart = await cart_service.get_or_create_cart(
        storefront_id=storefront.id,
        user_id=user_id,
        anonymous_id=anonymous_id,
    )
    
    # Update item quantity
    updated_item = await cart_service.update_item_quantity(
        cart_id=cart.id,
        item_id=item_id,
        quantity=request.quantity,
    )
    
    # Return updated cart
    return await get_cart(
        request=request,
        storefront=storefront,
        current_user=current_user,
        x_anonymous_id=anonymous_id,
        db=db,
        cart_service=cart_service,
    )


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from cart",
)
async def remove_cart_item(
    item_id: UUID,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
    db: AsyncSession = Depends(get_db),
    cart_service: CartService = Depends(get_cart_service),
) -> None:
    """
    Remove an item from the cart.
    
    Validates:
    - Item exists and belongs to the user's/anonymous cart
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    - X-Anonymous-ID: Optional anonymous identifier for guest users
    
    Returns 204 No Content on success.
    """
    if not current_user and not x_anonymous_id:
        raise BadRequestException(
            "Either authentication (JWT) or X-Anonymous-ID header is required to identify cart"
        )
    
    user_id = current_user.id if current_user else None
    anonymous_id = x_anonymous_id
    
    # Get or create cart
    cart = await cart_service.get_or_create_cart(
        storefront_id=storefront.id,
        user_id=user_id,
        anonymous_id=anonymous_id,
    )
    
    # Remove item
    success = await cart_service.remove_item(
        cart_id=cart.id,
        item_id=item_id,
    )
    
    if not success:
        raise NotFoundException("CartItem", item_id)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear all items from cart",
)
async def clear_cart(
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
    db: AsyncSession = Depends(get_db),
    cart_service: CartService = Depends(get_cart_service),
) -> None:
    """
    Remove all items from the cart.
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    - X-Anonymous-ID: Optional anonymous identifier for guest users
    
    Returns 204 No Content on success.
    """
    if not current_user and not x_anonymous_id:
        raise BadRequestException(
            "Either authentication (JWT) or X-Anonymous-ID header is required to identify cart"
        )
    
    user_id = current_user.id if current_user else None
    anonymous_id = x_anonymous_id
    
    # Get or create cart
    cart = await cart_service.get_or_create_cart(
        storefront_id=storefront.id,
        user_id=user_id,
        anonymous_id=anonymous_id,
    )
    
    # Clear cart
    await cart_service.clear_cart(cart.id)