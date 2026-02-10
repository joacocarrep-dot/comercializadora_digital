"""
PaymentServiceFactory for creating payment service instances.

Factory pattern implementation to create appropriate PaymentService
instances based on provider configuration and storefront settings.
"""
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentProvider
from app.models.storefront import Storefront
from app.core.exceptions import ConfigurationException, PaymentProviderException
from .base import PaymentService
from .mercadopago import MercadoPagoService


class PaymentServiceFactory:
    """
    Factory for creating payment service instances.
    
    Responsible for instantiating the appropriate PaymentService implementation
    based on provider configuration and storefront settings.
    """
    
    # Registry of available payment service implementations
    _service_registry: Dict[PaymentProvider, type] = {
        PaymentProvider.MERCADOPAGO: MercadoPagoService,
        # Future providers can be added here:
        # PaymentProvider.STRIPE: StripeService,
        # PaymentProvider.PAYPAL: PayPalService,
    }
    
    @classmethod
    def get_payment_service(
        cls,
        provider: PaymentProvider,
        storefront: Optional[Storefront] = None,
        **kwargs,
    ) -> PaymentService:
        """
        Get payment service instance for specified provider.
        
        Args:
            provider: Payment provider to use
            storefront: Storefront configuration (optional, for provider-specific config)
            **kwargs: Additional arguments to pass to service constructor
            
        Returns:
            Configured PaymentService instance
            
        Raises:
            ConfigurationException: If provider is not supported or misconfigured
            PaymentProviderException: If service cannot be instantiated
        """
        if provider not in cls._service_registry:
            raise ConfigurationException(
                f"Payment provider '{provider}' is not supported. "
                f"Available providers: {list(cls._service_registry.keys())}"
            )
        
        service_class = cls._service_registry[provider]
        
        try:
            # Get provider-specific configuration from storefront
            provider_config = cls._get_provider_config(provider, storefront)
            
            # Merge kwargs with provider config
            constructor_kwargs = {**provider_config, **kwargs}
            
            # Instantiate service
            instance = service_class(**constructor_kwargs)
            return instance
            
        except Exception as e:
            raise PaymentProviderException(
                f"Failed to create payment service for provider '{provider}': {str(e)}"
            ) from e
    
    @classmethod
    def get_payment_service_for_storefront(
        cls,
        storefront: Storefront,
        **kwargs,
    ) -> PaymentService:
        """
        Get payment service based on storefront configuration.
        
        Args:
            storefront: Storefront with payment_config specifying provider
            **kwargs: Additional arguments to pass to service constructor
            
        Returns:
            Configured PaymentService instance
            
        Raises:
            ConfigurationException: If storefront has no payment configuration
            PaymentProviderException: If service cannot be instantiated
        """
        if not storefront.payment_config:
            raise ConfigurationException(
                f"Storefront {storefront.id} has no payment configuration"
            )
        
        # Get provider from storefront configuration
        config = storefront.payment_config
        provider_name = config.get("provider")
        
        if not provider_name:
            raise ConfigurationException(
                f"Storefront {storefront.id} payment_config missing 'provider' field"
            )
        
        try:
            # Convert provider name string to enum
            provider = PaymentProvider(provider_name)
        except ValueError:
            raise ConfigurationException(
                f"Invalid payment provider '{provider_name}' in storefront {storefront.id} "
                f"configuration. Valid providers: {[p.value for p in PaymentProvider]}"
            )
        
        return cls.get_payment_service(provider, storefront, **kwargs)
    
    @classmethod
    def _get_provider_config(
        cls,
        provider: PaymentProvider,
        storefront: Optional[Storefront] = None,
    ) -> Dict[str, Any]:
        """
        Get provider-specific configuration.
        
        Args:
            provider: Payment provider
            storefront: Storefront configuration (optional)
            
        Returns:
            Dictionary of configuration parameters for service constructor
        """
        config = {}
        
        # Add sandbox mode based on environment or storefront config
        sandbox_mode = True  # Default to sandbox for development
        if storefront and storefront.payment_config:
            storefront_config = storefront.payment_config
            sandbox_mode = storefront_config.get("sandbox_mode", sandbox_mode)
        
        config["sandbox_mode"] = sandbox_mode
        
        # Add provider-specific configurations
        if provider == PaymentProvider.MERCADOPAGO:
            # MercadoPago-specific config
            config.update(cls._get_mercadopago_config(storefront))
        
        # Add other provider configs here as needed
        
        return config
    
    @classmethod
    def _get_mercadopago_config(cls, storefront: Optional[Storefront]) -> Dict[str, Any]:
        """
        Get MercadoPago-specific configuration.
        
        Args:
            storefront: Storefront configuration (optional)
            
        Returns:
            Dictionary with MercadoPago configuration
        """
        config = {}
        
        if storefront and storefront.payment_config:
            mp_config = storefront.payment_config.get("mercadopago", {})
            
            # Extract MercadoPago-specific settings
            # Note: access_token is handled by MercadoPagoService._get_sdk()
            # based on storefront.payment_config["mercadopago_access_token"]
            
            # Add any other MercadoPago-specific config here
            if "webhook_secret" in mp_config:
                config["webhook_secret"] = mp_config["webhook_secret"]
        
        return config
    
    @classmethod
    async def validate_storefront_payment_config(
        cls,
        session: AsyncSession,
        storefront: Storefront,
    ) -> Dict[str, Any]:
        """
        Validate storefront payment configuration.
        
        Args:
            session: Database session
            storefront: Storefront to validate
            
        Returns:
            Dictionary with validation results
            
        Raises:
            ConfigurationException: If configuration is invalid
        """
        if not storefront.payment_config:
            raise ConfigurationException("Storefront has no payment configuration")
        
        config = storefront.payment_config
        provider_name = config.get("provider")
        
        if not provider_name:
            raise ConfigurationException("Payment configuration missing 'provider' field")
        
        try:
            provider = PaymentProvider(provider_name)
        except ValueError:
            raise ConfigurationException(
                f"Invalid payment provider '{provider_name}'. "
                f"Valid providers: {[p.value for p in PaymentProvider]}"
            )
        
        validation_result = {
            "provider": provider.value,
            "is_valid": False,
            "errors": [],
            "warnings": [],
        }
        
        # Validate provider-specific configuration
        if provider == PaymentProvider.MERCADOPAGO:
            cls._validate_mercadopago_config(config, validation_result)
        # Add validation for other providers here
        
        # Check if configuration is complete
        validation_result["is_valid"] = len(validation_result["errors"]) == 0
        
        return validation_result
    
    @classmethod
    def _validate_mercadopago_config(
        cls,
        config: Dict[str, Any],
        validation_result: Dict[str, Any],
    ) -> None:
        """
        Validate MercadoPago configuration.
        
        Args:
            config: Storefront payment_config
            validation_result: Dictionary to update with validation results
        """
        # Check for required MercadoPago fields
        mp_config = config.get("mercadopago", {})
        
        if not mp_config.get("access_token"):
            validation_result["errors"].append(
                "MercadoPago configuration missing 'access_token'"
            )
        
        # Check for webhook secret (warning if missing in production)
        if not mp_config.get("webhook_secret"):
            validation_result["warnings"].append(
                "MercadoPago configuration missing 'webhook_secret'. "
                "Webhook verification will be disabled (insecure for production)."
            )
        
        # Check for base URL (warning if missing)
        if not config.get("base_url"):
            validation_result["warnings"].append(
                "Payment configuration missing 'base_url'. "
                "Callback URLs may not work correctly."
            )
    
    @classmethod
    def register_provider(
        cls,
        provider: PaymentProvider,
        service_class: type,
    ) -> None:
        """
        Register a new payment provider implementation.
        
        Args:
            provider: Payment provider enum
            service_class: PaymentService subclass implementing the provider
            
        Raises:
            ValueError: If service_class is not a subclass of PaymentService
        """
        if not issubclass(service_class, PaymentService):
            raise ValueError(
                f"Service class {service_class.__name__} must be a subclass of PaymentService"
            )
        
        cls._service_registry[provider] = service_class
    
    @classmethod
    def get_available_providers(cls) -> Dict[PaymentProvider, str]:
        """
        Get dictionary of available payment providers.
        
        Returns:
            Dictionary mapping provider enum to human-readable name
        """
        provider_names = {
            PaymentProvider.MERCADOPAGO: "MercadoPago",
            PaymentProvider.STRIPE: "Stripe",
            PaymentProvider.PAYPAL: "PayPal",
        }
        
        # Filter to only include providers with registered implementations
        available = {}
        for provider in cls._service_registry.keys():
            if provider in provider_names:
                available[provider] = provider_names[provider]
        
        return available