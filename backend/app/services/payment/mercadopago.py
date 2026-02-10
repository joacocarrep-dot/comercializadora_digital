"""
MercadoPago payment service implementation.

Concrete implementation of PaymentService for MercadoPago payment gateway.
Uses official MercadoPago SDK to create preferences, retrieve payments, and process webhooks.
"""
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

import mercadopago
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payment import Payment, PaymentStatus, PaymentProvider, PaymentEvent, PaymentEventType
from app.models.order import Order, OrderStatus
from app.models.storefront import Storefront
from app.models.order_item import OrderItem
from app.core.exceptions import (
    PaymentException,
    PaymentProviderException,
    PaymentNotFoundException,
    InvalidPaymentStateException,
    OrderNotFoundException,
    StorefrontNotFoundException,
    ConfigurationException,
)
from app.schemas.order import PaymentCreateRequest, PaymentResponse, WebhookNotification
from .base import PaymentService


class MercadoPagoService(PaymentService):
    """
    MercadoPago payment service implementation.
    
    Handles payment creation, status retrieval, and webhook processing
    for MercadoPago payment gateway.
    """
    
    def __init__(self, sandbox_mode: bool = True):
        """
        Initialize MercadoPago service.
        
        Args:
            sandbox_mode: Whether to use sandbox environment (default True for development)
        """
        self.sandbox_mode = sandbox_mode
        self.sdk = None  # Will be initialized with storefront-specific credentials
        self._init_sdk_placeholder()
    
    def _init_sdk_placeholder(self) -> None:
        """
        Placeholder for SDK initialization.
        
        In production, this would initialize the MercadoPago SDK with credentials
        from storefront.payment_config or environment variables.
        """
        # Actual initialization happens per-storefront in _get_sdk()
        pass
    
    def _get_sdk(self, storefront: Storefront) -> mercadopago.SDK:
        """
        Get MercadoPago SDK instance configured for storefront.
        
        Args:
            storefront: Storefront with payment_config containing credentials
            
        Returns:
            Configured MercadoPago SDK instance
            
        Raises:
            ConfigurationException: If storefront payment_config is missing required credentials
        """
        if not storefront.payment_config:
            raise ConfigurationException(
                f"Storefront {storefront.id} has no payment configuration"
            )
        
        config = storefront.payment_config
        access_token = config.get("mercadopago_access_token")
        
        if not access_token:
            raise ConfigurationException(
                f"Storefront {storefront.id} missing MercadoPago access_token in payment_config"
            )
        
        # Initialize SDK with storefront-specific credentials
        sdk = mercadopago.SDK(access_token)
        
        # Configure sandbox mode if specified
        if self.sandbox_mode:
            # Sandbox mode is typically controlled by the access token type
            # (test vs production tokens), but we can also set sandbox mode explicitly
            pass
        
        return sdk
    
    def get_provider_name(self) -> PaymentProvider:
        """Get the name of the payment provider."""
        return PaymentProvider.MERCADOPAGO
    
    async def create_payment(
        self,
        session: AsyncSession,
        order: Order,
        storefront: Storefront,
        request: PaymentCreateRequest,
    ) -> Payment:
        """
        Create a MercadoPago payment preference for an order.
        
        Args:
            session: Database session
            order: Order to create payment for
            storefront: Storefront making the payment
            request: Payment creation request
            
        Returns:
            Created Payment object with init_point for redirect
            
        Raises:
            OrderNotFoundException: If order not found or not in valid state
            PaymentProviderException: If MercadoPago fails to create preference
            PaymentException: If payment creation fails for business reasons
        """
        # Validate order state
        self._validate_order_for_payment(order)
        
        # Load order items with product/variant details
        from sqlalchemy import select
        stmt = (
            select(Order)
            .options(selectinload(Order.order_items).selectinload(OrderItem.product))
            .options(selectinload(Order.order_items).selectinload(OrderItem.variant))
            .where(Order.id == order.id)
        )
        result = await session.execute(stmt)
        order_with_items = result.scalar_one()
        
        # Calculate total amount from order (should match order.total)
        amount = order_with_items.total
        
        # Create payment record in database
        payment = Payment(
            order_id=order.id,
            storefront_id=storefront.id,
            provider=PaymentProvider.MERCADOPAGO,
            amount=amount,
            currency=order.currency or "ARS",
            status=PaymentStatus.PENDING,
            metadata={
                "sandbox": self.sandbox_mode,
                "payment_method": request.payment_method,
                "created_via": "api",
            },
        )
        
        session.add(payment)
        await session.flush()
        
        try:
            # Create MercadoPago preference
            sdk = self._get_sdk(storefront)
            preference_data = self._build_preference_data(
                order=order_with_items,
                payment=payment,
                storefront=storefront,
                request=request,
            )
            
            # Create preference in MercadoPago
            preference_result = sdk.preference().create(preference_data)
            
            if not preference_result.get("response"):
                raise PaymentProviderException(
                    f"MercadoPago failed to create preference: {preference_result.get('error', 'Unknown error')}"
                )
            
            preference = preference_result["response"]
            
            # Update payment with MercadoPago details
            payment.external_payment_id = preference.get("id")
            payment.init_point = preference.get("init_point")
            payment.metadata.update({
                "preference_id": preference.get("id"),
                "preference_data": preference,
            })
            
            # Create payment event
            await self._create_payment_event(
                session=session,
                payment=payment,
                event_type=PaymentEventType.PAYMENT_INITIATED,
                event_data={
                    "preference_id": preference.get("id"),
                    "init_point": preference.get("init_point"),
                    "sandbox_url": preference.get("sandbox_init_point"),
                    "items_count": len(order_with_items.order_items),
                    "amount": str(amount),
                },
                provider_event_id=preference.get("id"),
            )
            
            await session.flush()
            
            # Update order status to payment_pending
            order.status = OrderStatus.PAYMENT_PENDING
            order.payment_expires_at = datetime.utcnow() + timedelta(minutes=15)
            
            await session.flush()
            
            return payment
            
        except Exception as e:
            # Mark payment as failed
            payment.status = PaymentStatus.REJECTED
            await self._create_payment_event(
                session=session,
                payment=payment,
                event_type=PaymentEventType.PAYMENT_FAILED,
                event_data={"error": str(e)},
                error_message=f"Payment creation failed: {str(e)}",
            )
            await session.flush()
            
            if isinstance(e, PaymentProviderException):
                raise
            else:
                raise PaymentProviderException(
                    f"MercadoPago payment creation failed: {str(e)}"
                ) from e
    
    def _build_preference_data(
        self,
        order: Order,
        payment: Payment,
        storefront: Storefront,
        request: PaymentCreateRequest,
    ) -> Dict[str, Any]:
        """
        Build MercadoPago preference data from order.
        
        Args:
            order: Order with items
            payment: Payment record
            storefront: Storefront configuration
            request: Payment creation request
            
        Returns:
            Dictionary with MercadoPago preference data
        """
        # Base URL for callbacks (would come from storefront config or app settings)
        base_url = storefront.payment_config.get("base_url", "https://example.com")
        
        # Build items from order items
        items = []
        for item in order.order_items:
            item_data = {
                "id": str(item.product_id),
                "title": item.product_name or f"Product {item.product_id}",
                "quantity": item.quantity,
                "currency_id": order.currency or "ARS",
                "unit_price": float(item.unit_price),
            }
            
            if item.variant_id:
                item_data["description"] = f"Variant: {item.variant_name or item.variant_id}"
            
            items.append(item_data)
        
        # Add shipping cost as separate item if present
        if order.shipping_amount and order.shipping_amount > 0:
            items.append({
                "id": "shipping",
                "title": "Shipping Cost",
                "quantity": 1,
                "currency_id": order.currency or "ARS",
                "unit_price": float(order.shipping_amount),
            })
        
        preference_data = {
            "items": items,
            "payer": {
                "name": order.customer_first_name or "",
                "surname": order.customer_last_name or "",
                "email": order.customer_email or "",
            },
            "back_urls": {
                "success": urljoin(base_url, f"/checkout/success/{order.order_number}"),
                "failure": urljoin(base_url, f"/checkout/failure/{order.order_number}"),
                "pending": urljoin(base_url, f"/checkout/pending/{order.order_number}"),
            },
            "auto_return": "approved",
            "external_reference": str(order.id),
            "expires": True,
            "expiration_date_from": datetime.utcnow().isoformat() + "Z",
            "expiration_date_to": (datetime.utcnow() + timedelta(minutes=15)).isoformat() + "Z",
            "notification_url": urljoin(base_url, f"/webhooks/mercadopago/{storefront.id}"),
            "statement_descriptor": storefront.name[:22] if storefront.name else "Store",
            "metadata": {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "storefront_id": str(storefront.id),
                "payment_id": str(payment.id),
            },
        }
        
        # Add payment methods configuration if specified
        if request.payment_method:
            preference_data["payment_methods"] = {
                "excluded_payment_methods": [],
                "excluded_payment_types": [],
                "installments": 1,
            }
        
        return preference_data
    
    async def get_payment(
        self,
        session: AsyncSession,
        payment_id: uuid.UUID,
        storefront: Storefront,
    ) -> Payment:
        """
        Get payment details from MercadoPago.
        
        Args:
            session: Database session
            payment_id: Internal payment ID
            storefront: Storefront owning the payment
            
        Returns:
            Updated Payment object with latest status from MercadoPago
            
        Raises:
            PaymentNotFoundException: If payment not found
            PaymentProviderException: If MercadoPago fails to retrieve payment
        """
        from sqlalchemy import select
        
        # Get payment from database
        stmt = select(Payment).where(
            Payment.id == payment_id,
            Payment.storefront_id == storefront.id,
        )
        result = await session.execute(stmt)
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise PaymentNotFoundException(f"Payment {payment_id} not found")
        
        if not payment.external_payment_id:
            raise PaymentProviderException(
                f"Payment {payment_id} has no external payment ID"
            )
        
        try:
            # Get payment details from MercadoPago
            sdk = self._get_sdk(storefront)
            payment_result = sdk.payment().get(payment.external_payment_id)
            
            if not payment_result.get("response"):
                raise PaymentProviderException(
                    f"MercadoPago failed to retrieve payment: {payment_result.get('error', 'Unknown error')}"
                )
            
            mp_payment = payment_result["response"]
            
            # Map MercadoPago status to internal status
            mp_status = mp_payment.get("status", "pending")
            new_status = self._map_mercadopago_status(mp_status)
            
            # Update payment if status changed
            if payment.status != new_status:
                await self._update_payment_status(
                    session=session,
                    payment=payment,
                    new_status=new_status,
                    event_type=PaymentEventType.PAYMENT_STATUS_UPDATED,
                    event_data={
                        "mercadopago_status": mp_status,
                        "mercadopago_data": mp_payment,
                    },
                    provider_event_id=mp_payment.get("id"),
                )
            
            # Update payment method details if available
            if not payment.payment_method and mp_payment.get("payment_method_id"):
                payment.payment_method = mp_payment.get("payment_method_id")
            
            if not payment.card_last_four and mp_payment.get("card", {}).get("last_four_digits"):
                payment.card_last_four = mp_payment.get("card", {}).get("last_four_digits")
            
            await session.flush()
            return payment
            
        except Exception as e:
            await self._create_payment_event(
                session=session,
                payment=payment,
                event_type=PaymentEventType.PAYMENT_QUERY_FAILED,
                event_data={"error": str(e)},
                error_message=f"Failed to query payment from MercadoPago: {str(e)}",
            )
            await session.flush()
            
            if isinstance(e, PaymentProviderException):
                raise
            else:
                raise PaymentProviderException(
                    f"Failed to retrieve payment from MercadoPago: {str(e)}"
                ) from e
    
    async def process_webhook(
        self,
        session: AsyncSession,
        notification: WebhookNotification,
        storefront: Storefront,
        headers: Dict[str, str],
    ) -> Payment:
        """
        Process MercadoPago webhook notification.
        
        Args:
            session: Database session
            notification: Webhook notification data
            storefront: Storefront receiving the webhook
            headers: HTTP headers for signature verification
            
        Returns:
            Updated Payment object after processing webhook
            
        Raises:
            PaymentProviderException: If webhook verification fails
            InvalidPaymentStateException: If webhook data is invalid
            PaymentNotFoundException: If payment referenced in webhook not found
        """
        # Verify webhook signature (simplified - would use x-signature header in production)
        if not self._verify_webhook_signature(notification, headers, storefront):
            raise PaymentProviderException("Webhook signature verification failed")
        
        # Extract payment ID from notification
        payment_id = self._extract_payment_id_from_notification(notification)
        if not payment_id:
            raise InvalidPaymentStateException(
                "Webhook notification does not contain payment ID"
            )
        
        # Find payment by external_payment_id
        from sqlalchemy import select
        stmt = select(Payment).where(
            Payment.external_payment_id == payment_id,
            Payment.storefront_id == storefront.id,
        )
        result = await session.execute(stmt)
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise PaymentNotFoundException(
                f"Payment with external ID {payment_id} not found"
            )
        
        # Check for duplicate webhook (idempotency)
        if await self._is_duplicate_webhook(session, payment, notification):
            # Return existing payment without processing
            return payment
        
        # Create webhook received event
        await self._create_payment_event(
            session=session,
            payment=payment,
            event_type=PaymentEventType.WEBHOOK_RECEIVED,
            event_data={
                "notification": notification.model_dump(),
                "headers": headers,
            },
            provider_event_id=notification.id if hasattr(notification, "id") else None,
            processed_by="webhook",
        )
        
        # Get latest payment status from MercadoPago (don't trust notification alone)
        try:
            updated_payment = await self.get_payment(session, payment.id, storefront)
            
            # If payment is approved, trigger order fulfillment
            if updated_payment.status == PaymentStatus.APPROVED:
                await self._handle_payment_approved(session, updated_payment)
            
            # If payment is rejected/cancelled, release stock reservations
            elif updated_payment.status in [PaymentStatus.REJECTED, PaymentStatus.CANCELLED]:
                await self._handle_payment_failed(session, updated_payment)
            
            return updated_payment
            
        except Exception as e:
            await self._create_payment_event(
                session=session,
                payment=payment,
                event_type=PaymentEventType.WEBHOOK_PROCESSING_FAILED,
                event_data={"error": str(e)},
                error_message=f"Webhook processing failed: {str(e)}",
                processed_by="webhook",
            )
            raise PaymentProviderException(
                f"Failed to process webhook: {str(e)}"
            ) from e
    
    def _verify_webhook_signature(
        self,
        notification: WebhookNotification,
        headers: Dict[str, str],
        storefront: Storefront,
    ) -> bool:
        """
        Verify MercadoPago webhook signature.
        
        Args:
            notification: Webhook notification data
            headers: HTTP headers containing x-signature
            storefront: Storefront configuration
            
        Returns:
            True if signature is valid, False otherwise
        """
        # In production, this would verify the x-signature header
        # using the webhook secret from storefront.payment_config
        # For MVP, we'll accept all webhooks (in production this must be implemented!)
        
        # Placeholder implementation
        webhook_secret = storefront.payment_config.get("webhook_secret")
        if not webhook_secret:
            # No secret configured - accept webhook (dangerous in production!)
            return True
        
        # TODO: Implement proper signature verification
        # signature = headers.get("x-signature")
        # if not signature:
        #     return False
        # 
        # # Verify signature using webhook_secret
        # ...
        
        return True
    
    def _extract_payment_id_from_notification(
        self,
        notification: WebhookNotification,
    ) -> Optional[str]:
        """
        Extract payment ID from webhook notification.
        
        Args:
            notification: Webhook notification data
            
        Returns:
            MercadoPago payment ID or None if not found
        """
        # MercadoPago webhook format depends on notification type
        # For payment notifications, data.id contains the payment ID
        if hasattr(notification, "data") and notification.data:
            if isinstance(notification.data, dict):
                return notification.data.get("id")
            elif hasattr(notification.data, "id"):
                return notification.data.id
        
        # Try to extract from raw data
        if hasattr(notification, "model_dump"):
            data = notification.model_dump()
            if "data" in data and data["data"] and "id" in data["data"]:
                return data["data"]["id"]
        
        return None
    
    async def _is_duplicate_webhook(
        self,
        session: AsyncSession,
        payment: Payment,
        notification: WebhookNotification,
    ) -> bool:
        """
        Check if webhook is a duplicate based on provider_event_id.
        
        Args:
            session: Database session
            payment: Payment being processed
            notification: Webhook notification
            
        Returns:
            True if duplicate webhook, False otherwise
        """
        from sqlalchemy import select
        from app.models.payment import PaymentEvent
        
        # Extract provider_event_id from notification
        provider_event_id = None
        if hasattr(notification, "id"):
            provider_event_id = notification.id
        elif hasattr(notification, "data") and notification.data:
            if isinstance(notification.data, dict) and "id" in notification.data:
                provider_event_id = notification.data["id"]
        
        if not provider_event_id:
            return False
        
        # Check if we already have an event with this provider_event_id
        stmt = select(PaymentEvent).where(
            PaymentEvent.payment_id == payment.id,
            PaymentEvent.provider_event_id == provider_event_id,
        )
        result = await session.execute(stmt)
        existing_event = result.scalar_one_or_none()
        
        return existing_event is not None
    
    def _map_mercadopago_status(self, mp_status: str) -> PaymentStatus:
        """
        Map MercadoPago status to internal PaymentStatus.
        
        Args:
            mp_status: MercadoPago payment status
            
        Returns:
            Mapped PaymentStatus
        """
        status_mapping = {
            "pending": PaymentStatus.PENDING,
            "approved": PaymentStatus.APPROVED,
            "authorized": PaymentStatus.APPROVED,
            "in_process": PaymentStatus.IN_PROCESS,
            "in_mediation": PaymentStatus.IN_PROCESS,
            "rejected": PaymentStatus.REJECTED,
            "cancelled": PaymentStatus.CANCELLED,
            "refunded": PaymentStatus.REFUNDED,
            "charged_back": PaymentStatus.CHARGED_BACK,
            "failure": PaymentStatus.REJECTED,
            "expired": PaymentStatus.CANCELLED,
        }
        
        mp_status_lower = mp_status.lower()
        return status_mapping.get(mp_status_lower, PaymentStatus.PENDING)
    
    async def _handle_payment_approved(
        self,
        session: AsyncSession,
        payment: Payment,
    ) -> None:
        """
        Handle approved payment - confirm stock reservations and update order.
        
        Args:
            session: Database session
            payment: Approved payment
        """
        from app.services.order_service import OrderService
        from app.services.stock_reservation_service import StockReservationService
        from app.services.cart_service import CartService
        
        # Update order status to paid
        order_service = OrderService()
        await order_service.update_status(
            session=session,
            order_id=payment.order_id,
            new_status=OrderStatus.PAID,
            reason="payment_approved",
            changed_by="mercadopago_webhook",
        )
        
        # Confirm stock reservations
        reservation_service = StockReservationService()
        active_reservations = await reservation_service.get_active_reservations_for_order(
            session=session,
            order_id=payment.order_id,
        )
        
        for reservation in active_reservations:
            await reservation_service.confirm_reservation(
                session=session,
                reservation_id=reservation.id,
                confirmed_by="mercadopago_webhook",
            )
        
        # Clear user's cart if they have one
        # (This would require getting the order to find user_id)
        # For now, this is a placeholder
        
        # Create payment event for approval
        await self._create_payment_event(
            session=session,
            payment=payment,
            event_type=PaymentEventType.PAYMENT_APPROVED,
            event_data={
                "order_updated": True,
                "reservations_confirmed": len(active_reservations),
            },
            processed_by="webhook",
        )
    
    async def _handle_payment_failed(
        self,
        session: AsyncSession,
        payment: Payment,
    ) -> None:
        """
        Handle failed payment - release stock reservations and update order.
        
        Args:
            session: Database session
            payment: Failed payment
        """
        from app.services.order_service import OrderService
        from app.services.stock_reservation_service import StockReservationService
        
        # Update order status to cancelled
        order_service = OrderService()
        await order_service.update_status(
            session=session,
            order_id=payment.order_id,
            new_status=OrderStatus.CANCELLED,
            reason="payment_failed",
            changed_by="mercadopago_webhook",
        )
        
        # Release stock reservations
        reservation_service = StockReservationService()
        active_reservations = await reservation_service.get_active_reservations_for_order(
            session=session,
            order_id=payment.order_id,
        )
        
        for reservation in active_reservations:
            await reservation_service.release_reservation(
                session=session,
                reservation_id=reservation.id,
                reason="payment_failed",
                released_by="mercadopago_webhook",
            )
        
        # Create payment event for failure
        await self._create_payment_event(
            session=session,
            payment=payment,
            event_type=PaymentEventType.PAYMENT_FAILED,
            event_data={
                "order_cancelled": True,
                "reservations_released": len(active_reservations),
            },
            processed_by="webhook",
        )