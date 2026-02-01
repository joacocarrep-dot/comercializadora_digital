"""
Custom middleware for request processing.

Includes StorefrontMiddleware for API key authentication and
RequestLoggingMiddleware for request tracking.
"""
import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import AsyncSessionLocal
from app.core.exceptions import UnauthorizedException
from app.core.security import verify_password
from app.repositories.storefront_repo import StorefrontRepository

logger = logging.getLogger(__name__)


class StorefrontMiddleware(BaseHTTPMiddleware):
    """
    Middleware to identify storefront from X-API-Key header.
    
    Extracts API key from request header, verifies it against database,
    and injects storefront into request.state if valid.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and verify storefront API key.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler
            
        Returns:
            Response from next handler
            
        Raises:
            UnauthorizedException: If API key is invalid
        """
        # Skip authentication for health check and docs endpoints
        if request.url.path in ["/api/v1/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Skip authentication for admin endpoints (they use JWT)
        if request.url.path.startswith("/api/v1/admin"):
            return await call_next(request)
        
        # Extract API key from header
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            # For now, allow requests without API key (will be enforced in future phases)
            return await call_next(request)
        
        # Verify API key against database
        async with AsyncSessionLocal() as session:
            # Hashear el API key recibido
            from app.core.security import get_password_hash

            api_key_hash = get_password_hash(api_key)
            storefront = await storefront_repo.get_by_api_key_hash(api_key_hash)
            
            if not storefront or not storefront.is_active:
                raise UnauthorizedException("Invalid or inactive API key")
            
            # Inject storefront into request state
            request.state.storefront = storefront
        
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log requests and inject request ID.
    
    Generates unique request ID, logs request details,
    and adds request ID to response headers.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with logging and request ID injection.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler
            
        Returns:
            Response with X-Request-ID header
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request start
        start_time = time.time()
        logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"[Request ID: {request_id}]"
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log request completion
        logger.info(
            f"Request completed: {request.method} {request.url.path} "
            f"[Status: {response.status_code}] [Duration: {duration:.3f}s] "
            f"[Request ID: {request_id}]"
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
