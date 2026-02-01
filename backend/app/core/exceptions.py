"""
Custom exceptions and global exception handlers.

Defines application-specific exceptions and FastAPI exception handlers
for consistent error responses.
"""
from typing import Any, Dict

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class ComercializadoraException(Exception):
    """Base exception for all application-specific exceptions."""
    
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(ComercializadoraException):
    """Exception raised when a resource is not found."""
    
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} with identifier '{identifier}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedException(ComercializadoraException):
    """Exception raised when authentication fails."""
    
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(ComercializadoraException):
    """Exception raised when access is forbidden."""
    
    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class BadRequestException(ComercializadoraException):
    """Exception raised for invalid requests."""
    
    def __init__(self, message: str):
        super().__init__(
            code="BAD_REQUEST",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ConflictException(ComercializadoraException):
    """Exception raised when a resource conflict occurs."""
    
    def __init__(self, message: str):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


async def comercializadora_exception_handler(
    request: Request, exc: ComercializadoraException
) -> JSONResponse:
    """
    Handle custom application exceptions.
    
    Args:
        request: FastAPI request object
        exc: Custom exception instance
        
    Returns:
        JSON response with error details
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTP exceptions.
    
    Args:
        request: FastAPI request object
        exc: HTTP exception instance
        
    Returns:
        JSON response with error details
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
            }
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.
    
    Args:
        request: FastAPI request object
        exc: Exception instance
        
    Returns:
        JSON response with generic error message
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )
