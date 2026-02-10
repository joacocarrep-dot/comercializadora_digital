"""
Abstract PaymentService defining the interface for payment providers.

Implements Strategy pattern to allow different payment providers (MercadoPago, Stripe, etc.)
while maintaining a consistent interface for payment operations.
"""
import abc
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentStatus, PaymentProvider, PaymentEvent, PaymentEventType
from app.models.order import Order, OrderStatus
from app.models.storefront import Storefront
from app.core.exceptions import (
    PaymentException,
    PaymentProviderException,
    PaymentNotFoundException,
    InvalidPaymentStateException,
    OrderNotFoundException,
    StorefrontNotFoundException,
)
from app.schemas.order import PaymentCreateRequest, PaymentResponse, WebhookNotification


class PaymentService(abc.ABC):
    """
    Abstract base class for payment providers.
    
    All payment provider implementations must inherit from this class
    and implement the required methods.
    """
    
    @abc.abstractmethod
    async def create_payment(
        self,
        session: AsyncSession,
        order: Order,
        storefront: Storefront,
        request: PaymentCreateRequest,
    ) -> Payment:
        """
        Create a payment for an order.
        
        Args:
            session: Database session
            order: Order to create payment for
            storefront: Storefront making the payment
            request: Payment creation request
            
        Returns:
            Created Payment object with provider-specific details (init_point, external_payment_id, etc.)
            
        Raises:
            OrderNotFoundException: If order not found or not in valid state
            PaymentProviderException: If provider fails to create payment
            PaymentException: If payment creation fails for business reasons
        """
        pass
    
    @abc.abstractmethod
    async def get_payment(
        self,
        session: AsyncSession,
        payment_id: uuid.UUID,
        storefront: Storefront,
    ) -> Payment:
        """
        Get payment details from provider.
        
        Args:
            session: Database session
            payment_id: Internal payment ID
            storefront: Storefront owning the payment
            
        Returns:
            Updated Payment object with latest status from provider
            
        Raises:
            PaymentNotFoundException: If payment not found
            PaymentProviderException: If provider fails to retrieve payment
        """
        pass
    
    @abc.abstractmethod
    async def process_webhook(
        self,
        session: AsyncSession,
        notification: WebhookNotification,
        storefront: Storefront,
        headers: Dict[str, str],
    ) -> Payment:
        """
        Process webhook notification from payment provider.
        
        Args:
            session: Database session
            notification: Webhook notification data
            storefront: Storefront receiving the webhook
            headers: HTTP headers from webhook request (for signature verification)
            
        Returns:
            Updated Payment object after processing webhook
            
        Raises:
            PaymentProviderException: If webhook verification fails
            InvalidPaymentStateException: If webhook data is invalid
            PaymentNotFoundException: If payment referenced in webhook not found
        """
        pass
    
    @abc.abstractmethod
    def get_provider_name(self) -> PaymentProvider:
        """
        Get the name of the payment provider.
        
        Returns:
            PaymentProvider enum value for this service
        """
        pass
    
    async def _create_payment_event(
        self,
        session: AsyncSession,
        payment: Payment,
        event_type: PaymentEventType,
        event_data: Dict[str, Any],
        provider_event_id: Optional[str] = None,
        status_before: Optional[PaymentStatus] = None,
        status_after: Optional[PaymentStatus] = None,
        error_message: Optional[str] = None,
        processed_by: str = "system",
    ) -> PaymentEvent:
        """
        Create a payment event for audit trail.
        
        Args:
            session: Database session
            payment: Payment to create event for
            event_type: Type of event
            event_data: Event data as JSON-serializable dict
            provider_event_id: Provider's event ID (for deduplication)
            status_before: Payment status before event
            status_after: Payment status after event
            error_message: Error message if event failed
            processed_by: Who processed the event (system, webhook, admin, etc.)
            
        Returns:
            Created PaymentEvent object
        """
        payment_event = PaymentEvent(
            payment_id=payment.id,
            event_type=event_type,
            event_data=event_data,
            provider_event_id=provider_event_id,
            status_before=status_before or payment.status,
            status_after=status_after,
            error_message=error_message,
            processed_by=processed_by,
        )
        
        session.add(payment_event)
        await session.flush()
        return payment_event
    
    async def _update_payment_status(
        self,
        session: AsyncSession,
        payment: Payment,
        new_status: PaymentStatus,
        event_type: PaymentEventType,
        event_data: Dict[str, Any],
        provider_event_id: Optional[str] = None,
        webhook_received: bool = False,
    ) -> Payment:
        """
        Update payment status and create audit event.
        
        Args:
            session: Database session
            payment: Payment to update
            new_status: New payment status
            event_type: Event type for audit trail
            event_data: Event data
            provider_event_id: Provider's event ID
            webhook_received: Whether this update came from webhook
            
        Returns:
            Updated Payment object
        """
        old_status = payment.status
        payment.status = new_status
        
        if webhook_received:
            payment.webhook_received_at = datetime.utcnow()
        
        await self._create_payment_event(
            session=session,
            payment=payment,
            event_type=event_type,
            event_data=event_data,
            provider_event_id=provider_event_id,
            status_before=old_status,
            status_after=new_status,
        )
        
        await session.flush()
        return payment
    
    def _map_provider_status(self, provider_status: str) -> PaymentStatus:
        """
        Map provider-specific status to internal PaymentStatus.
        
        Args:
            provider_status: Status from payment provider
            
        Returns:
            Mapped PaymentStatus
            
        Raises:
            InvalidPaymentStateException: If provider status cannot be mapped
        """
        provider_status_lower = provider_status.lower()
        
        # Default mapping - can be overridden by subclasses
        mapping = {
            "pending": PaymentStatus.PENDING,
            "in_process": PaymentStatus.IN_PROCESS,
            "approved": PaymentStatus.APPROVED,
            "authorized": PaymentStatus.APPROVED,
            "rejected": PaymentStatus.REJECTED,
            "cancelled": PaymentStatus.CANCELLED,
            "refunded": PaymentStatus.REFUNDED,
            "charged_back": PaymentStatus.CHARGED_BACK,
            "failure": PaymentStatus.REJECTED,
            "expired": PaymentStatus.CANCELLED,
        }
        
        if provider_status_lower in mapping:
            return mapping[provider_status_lower]
        
        # Try partial matches
        for key, value in mapping.items():
            if key in provider_status_lower:
                return value
        
        raise InvalidPaymentStateException(
            f"Cannot map provider status '{provider_status}' to internal status"
        )
    
    def _validate_order_for_payment(self, order: Order) -> None:
        """
        Validate order is in correct state for payment creation.
        
        Args:
            order: Order to validate
            
        Raises:
            OrderNotFoundException: If order not found or not in valid state
            InvalidPaymentStateException: If order not in 'reserved' status
        """
        if order is None:
            raise OrderNotFoundException("Order not found")
        
        if order.status != OrderStatus.RESERVED:
            raise InvalidPaymentStateException(
                f"Order must be in 'reserved' status for payment, current status: {order.status}"
            )
        
        # Check if reservation is still valid
        if order.reservation_expires_at and order.reservation_expires_at < datetime.utcnow():
            raise InvalidPaymentStateException(
                "Order reservation has expired, cannot create payment"
            )