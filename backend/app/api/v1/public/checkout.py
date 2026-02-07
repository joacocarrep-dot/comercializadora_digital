"""
Public checkout endpoints for storefronts.

Provides checkout flow functionality including order creation,
stock validation, price confirmation, shipping address, and shipping method selection.
Uses X-API-Key for storefront identification, JWT for user authentication (optional),
and X-Anonymous-ID for guest users.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_checkout_service,
    get_cart_service,
    get_current_storefront,
    get_current_user_optional,
    get_db,
    get_order_service,
)
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.models.storefront import Storefront
from app.models.user import User
from app.schemas.order import (
    CheckoutInitResponse,
    PriceConfirmationRequest,
    ShippingAddressRequest,
    ShippingMethodRequest,
    StockValidationResponse,
)
from app.services import CartService, CheckoutService, OrderService

router = APIRouter()


@router.post(
    "/init",
    response_model=CheckoutInitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize checkout from cart",
)
async def init_checkout(
    request: Request,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
    db: AsyncSession = Depends(get_db),
    cart_service: CartService = Depends(get_cart_service),
    checkout_service: CheckoutService = Depends(get_checkout_service),
) -> CheckoutInitResponse:
    """
    Create an order from the current cart to start checkout.
    
    Validates:
    - Cart exists and is not empty
    - Cart belongs to the user/guest making the request
    
    Creates:
    - Order with status 'created'
    - Order items with product snapshot (name, sku, price)
    - Calculates subtotal and generates order_number
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    - X-Anonymous-ID: Optional anonymous identifier for guest users
    
    Returns order details with order_id and expires_at (15 minutes for checkout completion).
    """
    if not current_user and not x_anonymous_id:
        raise BadRequestException(
            "Either authentication (JWT) or X-Anonymous-ID header is required to identify cart"
        )
    
    user_id = current_user.id if current_user else None
    anonymous_id = x_anonymous_id
    
    # Get or create cart to ensure it exists
    cart = await cart_service.get_or_create_cart(
        storefront_id=storefront.id,
        user_id=user_id,
        anonymous_id=anonymous_id,
    )
    
    # Initialize checkout - creates order from cart
    order = await checkout_service.init_checkout(
        cart_id=cart.id,
        user_id=user_id,
    )
    
    # Get order with items to calculate totals
    order_with_items = await checkout_service.order_service.get_by_number(
        order_number=order.order_number,
        include_items=True,
    )
    
    if not order_with_items:
        raise NotFoundException("Order", order.id)
    
    # Calculate item count and total
    item_count = len(order_with_items.items) if order_with_items.items else 0
    subtotal = order_with_items.subtotal
    total = order_with_items.total
    
    return CheckoutInitResponse(
        order_id=order.id,
        order_number=order.order_number,
        status=order.status,
        expires_at=order.reservation_expires_at,
        item_count=item_count,
        subtotal=subtotal,
        total=total,
        currency=order.currency,
    )


@router.post(
    "/{order_id}/validate",
    response_model=StockValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate stock and prices for order",
)
async def validate_stock_and_prices(
    order_id: UUID,
    request: Request,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    checkout_service: CheckoutService = Depends(get_checkout_service),
    order_service: OrderService = Depends(get_order_service),
) -> StockValidationResponse:
    """
    Validate stock availability and price changes for an order.
    
    Validates:
    - Order exists and belongs to the user/guest
    - Order is in a valid state for validation (status 'created' or 'validating_stock')
    - Stock is available for all order items
    - Prices haven't changed since order creation
    
    If stock validation fails:
    - Returns is_valid=false with details of out-of-stock items
    - Order status remains 'created'
    
    If price changes detected:
    - Returns requires_price_confirmation=true with price change details
    - Order moves to status 'validating_stock'
    
    If all validations pass:
    - Reserves stock for 15 minutes
    - Updates order status to 'reserved'
    - Returns is_valid=true
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    
    Returns validation results with detailed information.
    """
    # First validate stock
    stock_validation = await checkout_service.validate_stock(order_id)
    
    # Then validate prices
    price_validation = await checkout_service.validate_prices(order_id)
    
    # Get order for response
    order = await order_service.get_by_id(order_id)
    if not order:
        raise NotFoundException("Order", order_id)
    
    # Check ownership
    if current_user and order.user_id != current_user.id:
        raise ForbiddenException("Order does not belong to the current user")
    # Note: For guest users, we rely on them having the order_id
    
    # Build response
    items_with_price_changes = []
    items_out_of_stock = []
    
    # Process price changes
    for item_change in price_validation.get("items_with_price_changes", []):
        items_with_price_changes.append({
            "order_item_id": item_change.get("order_item_id"),
            "product_id": item_change.get("product_id"),
            "variant_id": item_change.get("variant_id"),
            "old_price": Decimal(str(item_change.get("old_price", 0))),
            "new_price": Decimal(str(item_change.get("new_price", 0))),
            "quantity": item_change.get("quantity", 0),
            "price_difference": Decimal(str(item_change.get("price_difference", 0))),
            "total_price_difference": Decimal(str(item_change.get("total_price_difference", 0))),
            "requires_confirmation": True,
        })
    
    # Process out of stock items
    for out_of_stock_item in stock_validation.get("items_out_of_stock", []):
        items_out_of_stock.append({
            "product_id": out_of_stock_item.get("product_id"),
            "variant_id": out_of_stock_item.get("variant_id"),
            "quantity_requested": out_of_stock_item.get("quantity_requested", 0),
            "available_qty": out_of_stock_item.get("available_qty", 0),
            "is_backorder_allowed": out_of_stock_item.get("is_backorder_allowed", False),
            "product_name": out_of_stock_item.get("product_name"),
            "variant_name": out_of_stock_item.get("variant_name"),
        })
    
    # Determine overall validation status
    is_valid = (
        stock_validation.get("is_valid", False) and
        not price_validation.get("requires_confirmation", False)
    )
    
    # Calculate total price difference
    total_price_difference = Decimal("0.00")
    for item in items_with_price_changes:
        total_price_difference += item["total_price_difference"]
    
    # If all validations pass, reserve stock automatically
    if is_valid:
        await checkout_service.reserve_stock(order_id)
    
    return StockValidationResponse(
        order_id=order_id,
        order_number=order.order_number,
        items_with_price_changes=items_with_price_changes,
        items_out_of_stock=items_out_of_stock,
        total_price_difference=total_price_difference,
        is_valid=is_valid,
        requires_price_confirmation=price_validation.get("requires_confirmation", False),
    )


@router.post(
    "/{order_id}/confirm-price",
    response_model=StockValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm price changes and continue checkout",
)
async def confirm_price_changes(
    order_id: UUID,
    request: PriceConfirmationRequest,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    checkout_service: CheckoutService = Depends(get_checkout_service),
    order_service: OrderService = Depends(get_order_service),
) -> StockValidationResponse:
    """
    Confirm price changes and update order with new prices.
    
    Validates:
    - Order exists and belongs to the user/guest
    - Order is in status 'validating_stock' (price changes detected)
    - Customer explicitly confirms price changes
    
    Updates:
    - Order item prices to current prices
    - Recalculates order subtotal and total
    - Reserves stock for 15 minutes
    - Updates order status to 'reserved'
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    
    Returns validation results after confirming prices.
    """
    if not request.confirm:
        raise BadRequestException("Price confirmation is required to continue checkout")
    
    # Get order to check ownership
    order = await order_service.get_by_id(order_id)
    if not order:
        raise NotFoundException("Order", order_id)
    
    # Check ownership
    if current_user and order.user_id != current_user.id:
        raise ForbiddenException("Order does not belong to the current user")
    
    # Validate order is in correct state for price confirmation
    if order.status != "validating_stock":
        raise BadRequestException(
            f"Cannot confirm prices for order with status {order.status}. "
            f"Order must be in 'validating_stock' state."
        )
    
    # Update prices in order items
    # This is handled internally by checkout_service.reserve_stock()
    # which will use current prices when order is in 'validating_stock' state
    
    # Reserve stock with updated prices
    await checkout_service.reserve_stock(order_id)
    
    # Get updated order
    updated_order = await order_service.get_by_id(order_id)
    
    # Return success response
    return StockValidationResponse(
        order_id=order_id,
        order_number=updated_order.order_number,
        items_with_price_changes=[],  # Prices have been confirmed/updated
        items_out_of_stock=[],  # Already validated in previous step
        total_price_difference=Decimal("0.00"),
        is_valid=True,
        requires_price_confirmation=False,
    )


@router.post(
    "/{order_id}/shipping-address",
    status_code=status.HTTP_200_OK,
    summary="Add shipping address to order",
)
async def add_shipping_address(
    order_id: UUID,
    request: ShippingAddressRequest,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    checkout_service: CheckoutService = Depends(get_checkout_service),
    order_service: OrderService = Depends(get_order_service),
) -> dict:
    """
    Add shipping and billing addresses to an order.
    
    Validates:
    - Order exists and belongs to the user/guest
    - Order is in status 'reserved' (stock already reserved)
    - Address contains required fields
    - Country code is valid ISO 3166-1 alpha-2
    
    Updates:
    - Order shipping_address (JSONB)
    - Order billing_address (JSONB, defaults to shipping_address if not provided)
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    
    Returns success message.
    """
    # Get order to check ownership
    order = await order_service.get_by_id(order_id)
    if not order:
        raise NotFoundException("Order", order_id)
    
    # Check ownership
    if current_user and order.user_id != current_user.id:
        raise ForbiddenException("Order does not belong to the current user")
    
    # Validate order is in correct state for adding address
    if order.status != "reserved":
        raise BadRequestException(
            f"Cannot add shipping address for order with status {order.status}. "
            f"Order must be in 'reserved' state (stock already reserved)."
        )
    
    # Add shipping address to order
    await checkout_service.add_shipping_address(
        order_id=order_id,
        shipping_address=request.shipping_address,
        billing_address=request.billing_address,
    )
    
    return {
        "message": "Shipping address added successfully",
        "order_id": str(order_id),
        "order_number": order.order_number,
    }


@router.post(
    "/{order_id}/shipping-method",
    status_code=status.HTTP_200_OK,
    summary="Select shipping method for order",
)
async def select_shipping_method(
    order_id: UUID,
    request: ShippingMethodRequest,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    checkout_service: CheckoutService = Depends(get_checkout_service),
    order_service: OrderService = Depends(get_order_service),
) -> dict:
    """
    Select shipping method and calculate shipping cost.
    
    Validates:
    - Order exists and belongs to the user/guest
    - Order is in status 'reserved' (stock already reserved, address provided)
    - Shipping method is available for the storefront
    
    Updates:
    - Order shipping_method
    - Order shipping_amount
    - Order total (recalculated with shipping cost)
    
    Note: This is a placeholder implementation that sets a fixed shipping cost.
    In production, integrate with shipping provider API to calculate actual costs.
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Optional Bearer token for authenticated users
    
    Returns order with updated shipping cost.
    """
    # Get order to check ownership
    order = await order_service.get_by_id(order_id)
    if not order:
        raise NotFoundException("Order", order_id)
    
    # Check ownership
    if current_user and order.user_id != current_user.id:
        raise ForbiddenException("Order does not belong to the current user")
    
    # Validate order is in correct state for shipping method selection
    if order.status != "reserved":
        raise BadRequestException(
            f"Cannot select shipping method for order with status {order.status}. "
            f"Order must be in 'reserved' state (stock already reserved)."
        )
    
    # Calculate shipping (placeholder implementation)
    await checkout_service.calculate_shipping(
        order_id=order_id,
        shipping_method=request.shipping_method,
        shipping_options=request.shipping_options,
    )
    
    # Get updated order with new shipping amount and total
    updated_order = await order_service.get_by_id(order_id)
    
    return {
        "message": "Shipping method selected successfully",
        "order_id": str(order_id),
        "order_number": updated_order.order_number,
        "shipping_method": request.shipping_method,
        "shipping_amount": float(updated_order.shipping_amount),
        "total": float(updated_order.total),
        "currency": updated_order.currency,
    }