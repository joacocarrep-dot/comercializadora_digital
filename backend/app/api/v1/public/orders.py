"""
Public order endpoints for storefronts.

Provides order history and order details for authenticated users.
Uses X-API-Key for storefront identification and JWT for user authentication.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_storefront,
    get_current_user_optional,
    get_db,
    get_order_service,
)
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.models.storefront import Storefront
from app.models.user import User
from app.schemas.order import (
    OrderListPaginated,
    OrderResponse,
    OrderSummary,
)
from app.services import OrderService

router = APIRouter()


@router.get(
    "",
    response_model=OrderListPaginated,
    status_code=status.HTTP_200_OK,
    summary="List orders for authenticated user",
)
async def list_orders(
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(
        None, 
        description="Filter by order status (comma-separated for multiple statuses)"
    ),
    db: AsyncSession = Depends(get_db),
    order_service: OrderService = Depends(get_order_service),
) -> OrderListPaginated:
    """
    Get paginated list of orders for the authenticated user.
    
    Returns orders belonging to the current user within the current storefront.
    Supports pagination and optional status filtering.
    
    Validates:
    - User is authenticated (JWT required)
    - User has access to orders in the current storefront
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Required Bearer token for user authentication
    
    Returns paginated list of order summaries.
    """
    # Require authenticated user for order listing
    if not current_user:
        raise UnauthorizedException("Authentication required to access orders")
    
    # Parse status filter if provided
    statuses = None
    if status_filter:
        statuses = [s.strip().lower() for s in status_filter.split(",") if s.strip()]
        # Validate statuses are valid OrderStatus values
        valid_statuses = {
            "created", "validating_stock", "reserved", "payment_pending", 
            "paid", "processing", "completed", "cancelled"
        }
        for status_val in statuses:
            if status_val not in valid_statuses:
                raise BadRequestException(
                    f"Invalid order status: {status_val}. "
                    f"Valid statuses: {', '.join(sorted(valid_statuses))}"
                )
    
    # Get orders for user in this storefront
    orders_result = await order_service.get_by_user(
        user_id=current_user.id,
        storefront_id=storefront.id,
        page=page,
        per_page=per_page,
        statuses=statuses,
    )
    
    # Transform to response format
    order_summaries = []
    for order in orders_result["orders"]:
        # Count items
        item_count = 0
        if hasattr(order, "items") and order.items:
            item_count = len(order.items)
        elif hasattr(order, "item_count"):
            item_count = order.item_count
        
        # Create summary
        summary = OrderSummary(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            subtotal=order.subtotal,
            shipping_amount=order.shipping_amount,
            tax_amount=order.tax_amount,
            total=order.total,
            currency=order.currency,
            created_at=order.created_at,
            updated_at=order.updated_at,
            item_count=item_count,
        )
        order_summaries.append(summary)
    
    return OrderListPaginated(
        orders=order_summaries,
        total=orders_result["total"],
        page=page,
        per_page=per_page,
        total_pages=orders_result["total_pages"],
        has_next=orders_result["has_next"],
        has_prev=orders_result["has_prev"],
    )


@router.get(
    "/{order_number}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get order details by order number",
)
async def get_order_by_number(
    order_number: str,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    include_items: bool = Query(default=True, description="Include order items in response"),
    include_status_history: bool = Query(default=False, description="Include status history in response"),
    include_reservations: bool = Query(default=False, description="Include stock reservations in response"),
    db: AsyncSession = Depends(get_db),
    order_service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    """
    Get detailed order information by order number.
    
    Returns complete order details including items, status history, and stock reservations.
    Order must belong to the authenticated user and be within the current storefront.
    
    Validates:
    - User is authenticated (JWT required)
    - Order exists and belongs to the current user
    - Order is within the current storefront
    
    Headers:
    - X-API-Key: Required for storefront identification
    - Authorization: Required Bearer token for user authentication
    
    Returns complete order details with optional includes.
    """
    # Require authenticated user for order details
    if not current_user:
        raise UnauthorizedException("Authentication required to access order details")
    
    # Build include options
    include_options = []
    if include_items:
        include_options.append("items")
    if include_status_history:
        include_options.append("status_history")
    if include_reservations:
        include_options.append("stock_reservations")
    
    # Get order with optional includes
    order = await order_service.get_by_number(
        order_number=order_number,
        include_items=include_items,
        include_status_history=include_status_history,
        include_reservations=include_reservations,
    )
    
    if not order:
        raise NotFoundException("Order", order_number)
    
    # Verify order belongs to current user
    if order.user_id != current_user.id:
        raise ForbiddenException("Order does not belong to the current user")
    
    # Verify order is within current storefront
    if order.storefront_id != storefront.id:
        raise ForbiddenException("Order does not belong to the current storefront")
    
    # Transform addresses from JSONB to dict if they exist
    shipping_address = None
    if order.shipping_address:
        shipping_address = order.shipping_address
    
    billing_address = None
    if order.billing_address:
        billing_address = order.billing_address
    
    # Transform items if included
    items = None
    if include_items and order.items:
        from app.schemas.order import OrderItemResponse
        items = []
        for item in order.items:
            item_response = OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                product_sku=item.product_sku,
                variant_id=item.variant_id,
                variant_name=item.variant_name,
                variant_sku=item.variant_sku,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.total_price,
            )
            items.append(item_response)
    
    # Transform status history if included
    status_history = None
    if include_status_history and order.status_history:
        from app.schemas.order import OrderStatusHistoryResponse
        status_history = []
        for history in order.status_history:
            history_response = OrderStatusHistoryResponse(
                id=history.id,
                from_status=history.from_status,
                to_status=history.to_status,
                reason=history.reason,
                notes=history.notes,
                changed_by=history.changed_by,
                changed_at=history.changed_at,
            )
            status_history.append(history_response)
    
    # Transform stock reservations if included
    stock_reservations = None
    if include_reservations and order.stock_reservations:
        from app.schemas.order import StockReservationSummary
        stock_reservations = []
        for reservation in order.stock_reservations:
            reservation_summary = StockReservationSummary(
                id=reservation.id,
                inventory_id=reservation.inventory_id,
                quantity=reservation.quantity,
                expires_at=reservation.expires_at,
                status=reservation.status,
            )
            stock_reservations.append(reservation_summary)
    
    # Prepare metadata if exists
    metadata = None
    if order.metadata:
        metadata = order.metadata
    
    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        storefront_id=order.storefront_id,
        user_id=order.user_id,
        status=order.status,
        subtotal=order.subtotal,
        shipping_amount=order.shipping_amount,
        tax_amount=order.tax_amount,
        total=order.total,
        currency=order.currency,
        shipping_address=shipping_address,
        billing_address=billing_address,
        created_at=order.created_at,
        updated_at=order.updated_at,
        reserved_at=order.reserved_at,
        reservation_expires_at=order.reservation_expires_at,
        metadata=metadata,
        items=items,
        status_history=status_history,
        stock_reservations=stock_reservations,
    )