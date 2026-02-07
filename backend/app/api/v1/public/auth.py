"""
Public authentication endpoints for customers.

Provides OTP-based authentication, OAuth social login, token management,
and customer profile operations for storefronts.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_storefront,
    get_db,
    get_auth_service,
    get_user_service,
    get_otp_service,
    get_current_user_optional,
)
from app.core.exceptions import BadRequestException, UnauthorizedException
from app.models.storefront import Storefront
from app.models.user import User, UserType
from app.models.oauth_connection import OAuthProvider
from app.models.otp_code import OTPPurpose
from app.schemas.auth import (
    OTPRequest,
    OTPResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
    OAuthProvider as OAuthProviderEnum,
    OAuthResponse,
    RefreshTokenRequest,
    ProfileUpdateRequest,
    UserResponse,
)
from app.services import AuthService, UserService, OTPService

router = APIRouter()


@router.post(
    "/request-code",
    response_model=OTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Request OTP code for customer authentication",
)
async def request_otp_code(
    request_data: OTPRequest,
    storefront: Storefront = Depends(get_current_storefront),
    auth_service: AuthService = Depends(get_auth_service),
) -> OTPResponse:
    """
    Request a 6-digit OTP code for customer authentication via email or phone.
    
    Generates and sends a one-time password to the provided email or phone.
    The code expires in 10 minutes. Rate limiting applies to prevent abuse.
    
    Headers:
    - X-API-Key: Storefront API key (required)
    
    Body:
    - email: Optional email address
    - phone: Optional phone number (E.164 format)
    
    Note: Either email or phone must be provided.
    """
    if not request_data.email and not request_data.phone:
        raise BadRequestException("Either email or phone must be provided")
    
    # Request OTP through auth service
    result = await auth_service.request_otp(
        email=request_data.email,
        phone=request_data.phone,
        storefront_id=storefront.id,
        purpose=OTPPurpose.LOGIN,
    )
    
    return OTPResponse(**result)


@router.post(
    "/verify-code",
    response_model=OTPVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP code and authenticate customer",
)
async def verify_otp_code(
    request_data: OTPVerifyRequest,
    storefront: Storefront = Depends(get_current_storefront),
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
) -> OTPVerifyResponse:
    """
    Verify OTP code and authenticate customer.
    
    Validates the 6-digit code, creates or retrieves the customer account,
    generates JWT tokens, and optionally links anonymous cart to the user.
    
    Headers:
    - X-API-Key: Storefront API key (required)
    - X-Anonymous-ID: Optional anonymous cart ID for cart linking
    
    Body:
    - email: Optional email address used for OTP
    - phone: Optional phone number used for OTP
    - code: 6-digit verification code
    
    Note: Either email or phone must be provided.
    """
    if not request_data.email and not request_data.phone:
        raise BadRequestException("Either email or phone must be provided")
    
    # Verify OTP and authenticate user
    user, auth_result = await auth_service.verify_otp(
        email=request_data.email,
        phone=request_data.phone,
        code=request_data.code,
        storefront_id=storefront.id,
        anonymous_cart_id=x_anonymous_id,
    )
    
    # Convert user to UserResponse schema
    user_response = UserResponse.from_orm(user)
    
    return OTPVerifyResponse(
        access_token=auth_result["access_token"],
        token_type=auth_result["token_type"],
        expires_in=auth_result["expires_in"],
        user=user_response,
        cart_linked=auth_result["cart_linked"],
    )


@router.get(
    "/oauth/{provider}",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    summary="Initiate OAuth login with social provider",
)
async def oauth_login_start(
    provider: OAuthProviderEnum,
    request: Request,
    storefront: Storefront = Depends(get_current_storefront),
) -> RedirectResponse:
    """
    Start OAuth login flow by redirecting to social provider.
    
    This endpoint initiates the OAuth flow by redirecting the user to the
    specified provider's authorization page. The provider must be one of:
    google, facebook, or apple.
    
    Headers:
    - X-API-Key: Storefront API key (required)
    
    Path parameters:
    - provider: OAuth provider (google, facebook, apple)
    
    Query parameters (optional):
    - state: Custom state parameter for CSRF protection
    - redirect_uri: Custom redirect URI for OAuth callback
    
    Note: This is a placeholder implementation. In production, this would
    construct the proper OAuth authorization URL with client ID, scopes,
    and state parameters.
    """
    # Placeholder implementation
    # In production, this would:
    # 1. Generate CSRF state token and store in session/cache
    # 2. Build provider-specific authorization URL
    # 3. Redirect user to provider's authorization page
    
    # For now, return a 501 Not Implemented response
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"OAuth login for {provider} is not yet implemented. "
               "This endpoint would redirect to the provider's authorization page.",
    )


@router.get(
    "/oauth/{provider}/callback",
    response_model=OAuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Handle OAuth callback and authenticate user",
)
async def oauth_login_callback(
    provider: OAuthProviderEnum,
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None,
    storefront: Storefront = Depends(get_current_storefront),
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
    auth_service: AuthService = Depends(get_auth_service),
) -> OAuthResponse:
    """
    Handle OAuth callback from social provider.
    
    Processes the authorization code returned by the OAuth provider,
    exchanges it for access tokens, retrieves user profile information,
    and authenticates or creates the customer account.
    
    Headers:
    - X-API-Key: Storefront API key (required)
    - X-Anonymous-ID: Optional anonymous cart ID for cart linking
    
    Query parameters:
    - code: Authorization code from OAuth provider (required)
    - state: CSRF state token for verification (optional)
    - error: Error from OAuth provider (optional)
    
    Path parameters:
    - provider: OAuth provider (google, facebook, apple)
    
    Note: This is a placeholder implementation. In production, this would
    integrate with OAuth libraries (Authlib) to exchange code for tokens
    and retrieve user profile information.
    """
    if error:
        raise BadRequestException(f"OAuth error from provider: {error}")
    
    if not code:
        raise BadRequestException("Authorization code is required")
    
    # Placeholder implementation
    # In production, this would:
    # 1. Verify CSRF state token
    # 2. Exchange authorization code for access token
    # 3. Retrieve user profile from provider API
    # 4. Call auth_service.oauth_login()
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"OAuth callback for {provider} is not yet implemented. "
               "This endpoint would exchange code for tokens and authenticate user.",
    )


@router.post(
    "/refresh",
    response_model=OTPVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token using refresh token",
)
async def refresh_token(
    request_data: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> OTPVerifyResponse:
    """
    Refresh access token using a refresh token.
    
    Exchanges a valid refresh token for a new access token.
    This endpoint is for future implementation - MVP uses stateless JWT
    without refresh tokens.
    
    Body:
    - refresh_token: Refresh token string
    
    Note: This endpoint returns a 400 error in MVP as refresh tokens are
    not implemented. This is a placeholder for future development.
    """
    # MVP doesn't implement refresh tokens
    # This would call auth_service.refresh_access_token() in production
    
    raise BadRequestException(
        "Refresh tokens are not implemented in MVP. "
        "Please re-authenticate using OTP or OAuth."
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout user and invalidate refresh token",
)
async def logout(
    request_data: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """
    Logout user and invalidate refresh token.
    
    Invalidates the provided refresh token to prevent further use.
    This endpoint is for future implementation - MVP uses stateless JWT
    without refresh token blacklist.
    
    Body:
    - refresh_token: Refresh token to invalidate
    
    Note: This endpoint returns a 400 error in MVP as refresh tokens are
    not implemented. This is a placeholder for future development.
    """
    # MVP doesn't implement refresh token blacklist
    # This would invalidate the refresh token in production
    
    raise BadRequestException(
        "Logout with refresh token invalidation is not implemented in MVP. "
        "Tokens are stateless and cannot be invalidated before expiration."
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated customer profile",
)
async def get_current_profile(
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> UserResponse:
    """
    Get profile information for the currently authenticated customer.
    
    Returns detailed customer information including contact details,
    verification status, and profile information.
    
    Headers:
    - X-API-Key: Storefront API key (required)
    - Authorization: Bearer token (optional, returns 401 if not provided)
    
    Returns 401 Unauthorized if no valid authentication token is provided.
    """
    if not current_user:
        raise UnauthorizedException("Authentication required")
    
    # Verify user is a customer and belongs to this storefront
    if current_user.user_type != UserType.CUSTOMER:
        raise UnauthorizedException("Only customer users can access this endpoint")
    
    if current_user.storefront_id != storefront.id:
        raise UnauthorizedException("User does not belong to this storefront")
    
    return UserResponse.from_orm(current_user)


@router.put(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current customer profile",
)
async def update_profile(
    request_data: ProfileUpdateRequest,
    storefront: Storefront = Depends(get_current_storefront),
    current_user: Optional[User] = Depends(get_current_user_optional),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Update profile information for the currently authenticated customer.
    
    Allows customers to update their name and contact information.
    Changing email or phone requires verification through OTP.
    
    Headers:
    - X-API-Key: Storefront API key (required)
    - Authorization: Bearer token (required)
    
    Body:
    - first_name: Optional new first name
    - last_name: Optional new last name
    - email: Optional new email (requires verification)
    - phone: Optional new phone (requires verification)
    
    Returns 401 Unauthorized if no valid authentication token is provided.
    """
    if not current_user:
        raise UnauthorizedException("Authentication required")
    
    # Verify user is a customer and belongs to this storefront
    if current_user.user_type != UserType.CUSTOMER:
        raise UnauthorizedException("Only customer users can access this endpoint")
    
    if current_user.storefront_id != storefront.id:
        raise UnauthorizedException("User does not belong to this storefront")
    
    # Update profile using user service
    updated_user = await user_service.update_profile(
        user_id=current_user.id,
        first_name=request_data.first_name,
        last_name=request_data.last_name,
        email=request_data.email,
        phone=request_data.phone,
    )
    
    return UserResponse.from_orm(updated_user)