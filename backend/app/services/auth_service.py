"""
Authentication service for customer login via OTP and OAuth.

Handles OTP request/verification, OAuth login flows, token creation,
and refresh token management for customer authentication.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, UnauthorizedException
from app.core.security import create_access_token, decode_access_token
from app.models.otp_code import OTPCode, OTPPurpose
from app.models.oauth_connection import OAuthConnection, OAuthProvider
from app.models.user import User, UserType
from app.services.otp_service import OTPService
from app.services.user_service import UserService
from app.repositories.oauth_repo import OAuthRepository
from app.repositories.base import BaseRepository


class AuthService:
    """
    Service for authentication business logic operations.

    Attributes:
        session: Async database session
        otp_service: OTPService for OTP operations
        user_service: UserService for user management
        oauth_repo: OAuthRepository for OAuth connection operations
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize auth service with database session.

        Args:
            session: Async database session
        """
        self.session = session
        self.otp_service = OTPService(session)
        self.user_service = UserService(session)
        self.oauth_repo = OAuthRepository(session)
        self.user_repo = BaseRepository(User, session)

    async def request_otp(
        self,
        storefront_id: uuid.UUID,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        purpose: OTPPurpose = OTPPurpose.LOGIN,
    ) -> Dict[str, Any]:
        """
        Request OTP code for customer authentication.

        Generates and sends OTP code via preferred channel.
        Implements rate limiting and validation.

        Args:
            email: Email address (optional if phone provided)
            phone: Phone number (optional if email provided)
            storefront_id: Storefront UUID for scoping
            purpose: Purpose of OTP code (default: login)

        Returns:
            Dictionary with OTP request results
        """
        if not email and not phone:
            raise BadRequestException("Either email or phone must be provided")

        # Generate OTP code
        otp_code = await self.otp_service.generate_code(
            email=email,
            phone=phone,
            purpose=purpose,
            storefront_id=storefront_id,
            expires_in_minutes=10,
        )

        # Determine preferred channel based on contact type
        channel = "email" if email else "whatsapp"

        # Send code (placeholder implementation)
        send_result = await self.otp_service.send_code(otp_code, channel=channel)

        # Prepare response (exclude actual code in production)
        response = {
            "message": "Verification code sent successfully",
            "contact": email if email else phone,
            "contact_type": "email" if email else "phone",
            "channel": channel,
            "expires_in": 600,  # 10 minutes in seconds
            "purpose": purpose.value,
            "code_id": str(otp_code.id),
            "simulated": send_result.get("simulated", True),  # Indicate placeholder
        }

        return response

    async def verify_otp(
        self,
        storefront_id: uuid.UUID,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        code: str = "",
        anonymous_cart_id: Optional[str] = None,
    ) -> Tuple[User, Dict[str, Any]]:
        """
        Verify OTP code and authenticate customer.

        Validates OTP, creates/retrieves user, generates tokens,
        and handles cart linking if anonymous_cart_id provided.

        Args:
            email: Email address (optional if phone provided)
            phone: Phone number (optional if email provided)
            code: 6-digit verification code
            storefront_id: Storefront UUID for scoping
            anonymous_cart_id: Optional anonymous cart ID for linking

        Returns:
            Tuple of (User instance, token response dictionary)

        Raises:
            BadRequestException: If OTP validation fails
        """
        if not email and not phone:
            raise BadRequestException("Either email or phone must be provided")

        # Validate OTP code
        otp_code = await self.otp_service.validate_code(
            email=email,
            phone=phone,
            code=code,
            purpose=OTPPurpose.LOGIN,
            storefront_id=storefront_id,
        )

        # Determine which contact was verified
        contact_verified = "email" if email else "phone"
        contact_value = email if email else phone

        # Get or create user
        if email:
            user = await self.user_service.get_or_create_by_email(
                email=email,
                storefront_id=storefront_id,
                email_verified=True,  # Auto-verify on successful OTP
            )
        else:  # phone
            # For phone, we need to handle differently
            # Try to find existing user by phone
            from app.repositories.user_repo import UserRepository
            user_repo = UserRepository(self.session)
            user = await user_repo.find_by_phone_and_storefront(
                phone=phone,
                storefront_id=storefront_id,
                user_type=UserType.CUSTOMER,
            )

            if not user:
                # Create new user with phone
                user = await self.user_service.create_user(
                    phone=phone,
                    storefront_id=storefront_id,
                    phone_verified=True,  # Auto-verify on successful OTP
                )
            else:
                # Update verification status
                if not user.phone_verified:
                    user = await self.user_service.verify_phone(user.id)

        # Update verification status based on which contact was verified
        if contact_verified == "email" and not user.email_verified:
            user = await self.user_service.verify_email(user.id)
        elif contact_verified == "phone" and not user.phone_verified:
            user = await self.user_service.verify_phone(user.id)

        # Generate tokens
        tokens = await self.create_tokens(user)

        # Handle cart linking (placeholder - would integrate with CartService)
        cart_linked = False
        if anonymous_cart_id:
            # This would call CartService.merge_carts or similar
            # For now, just indicate it would happen
            cart_linked = True

        # Prepare response
        response = {
            "access_token": tokens["access_token"],
            "token_type": "bearer",
            "expires_in": tokens["expires_in"],
            "user": {
                "id": str(user.id),
                "email": user.email,
                "phone": user.phone,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email_verified": user.email_verified,
                "phone_verified": user.phone_verified,
            },
            "cart_linked": cart_linked,
        }

        return user, response

    async def oauth_login(
        self,
        storefront_id: uuid.UUID,
        provider: OAuthProvider,
        provider_id: str,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        profile_picture: Optional[str] = None,
        anonymous_cart_id: Optional[str] = None,
    ) -> Tuple[User, Dict[str, Any]]:
        """
        Handle OAuth login for social providers.

        Creates or links OAuth connection, creates/retrieves user,
        generates tokens, and handles cart linking.

        Args:
            provider: OAuth provider (google, facebook, apple)
            provider_id: External provider user ID
            email: Email from OAuth provider
            first_name: Optional first name from provider
            last_name: Optional last name from provider
            profile_picture: Optional profile picture URL
            storefront_id: Storefront UUID for scoping
            anonymous_cart_id: Optional anonymous cart ID for linking

        Returns:
            Tuple of (User instance, token response dictionary)
        """
        # Check for existing OAuth connection
        oauth_connection = await self.oauth_repo.find_by_provider_and_id(
            provider=provider,
            provider_id=provider_id,
        )

        if oauth_connection:
            # Existing connection - get user
            user = await self.user_repo.get_by_id(oauth_connection.user_id)
            if not user or not user.is_active:
                raise UnauthorizedException("User account not found or inactive")

            # Update connection with latest tokens/profile info
            await self.oauth_repo.update_tokens(
                connection_id=oauth_connection.id,
                # In real implementation, would update with new tokens
            )
        else:
            # New OAuth connection
            # Try to find user by email in this storefront
            from app.repositories.user_repo import UserRepository
            user_repo = UserRepository(self.session)
            user = await user_repo.find_by_email_and_storefront(
                email=email,
                storefront_id=storefront_id,
                user_type=UserType.CUSTOMER,
            )

            if user:
                # Link OAuth to existing user
                user = await self.user_service.link_oauth_account(
                    user_id=user.id,
                    oauth_provider=provider.value,
                    oauth_id=provider_id,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
            else:
                # Create new user with OAuth
                user = await self.user_service.create_user(
                    email=email,
                    storefront_id=storefront_id,
                    first_name=first_name,
                    last_name=last_name,
                    email_verified=True,  # OAuth emails are considered verified
                    oauth_provider=provider.value,
                    oauth_id=provider_id,
                )

            # Create OAuth connection record
            connection_data = {
                "user_id": user.id,
                "provider": provider,
                "provider_id": provider_id,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "profile_picture": profile_picture,
                # In real implementation, would store access/refresh tokens
            }
            await self.oauth_repo.create(**connection_data)

        # Generate tokens
        tokens = await self.create_tokens(user)

        # Handle cart linking (placeholder)
        cart_linked = False
        if anonymous_cart_id:
            cart_linked = True

        # Prepare response
        response = {
            "access_token": tokens["access_token"],
            "token_type": "bearer",
            "expires_in": tokens["expires_in"],
            "user": {
                "id": str(user.id),
                "email": user.email,
                "phone": user.phone,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email_verified": user.email_verified,
                "phone_verified": user.phone_verified,
                "oauth_provider": user.oauth_provider,
            },
            "cart_linked": cart_linked,
        }

        return user, response

    async def create_tokens(self, user: User) -> Dict[str, Any]:
        """
        Create access token for customer user.

        Generates JWT with customer-specific claims.
        Note: MVP uses stateless JWT without refresh tokens.

        Args:
            user: User instance

        Returns:
            Dictionary with token information
        """
        # Validate user is a customer
        if user.user_type != UserType.CUSTOMER:
            raise BadRequestException("Only customer users can use this authentication")

        if not user.storefront_id:
            raise BadRequestException("Customer must have storefront_id")

        # Create access token with 24h expiration
        # Note: Using create_access_token from security.py, but it expects role
        # We'll need to adapt or create a customer-specific token function
        # For now, use a placeholder role
        access_token = create_access_token(
            user_id=user.id,
            role=None,  # Customers don't have admin roles
            storefront_id=user.storefront_id,
        )

        # Decode to get expiration
        decoded = decode_access_token(access_token)
        expires_at = datetime.fromtimestamp(decoded["exp"])

        return {
            "access_token": access_token,
            "expires_in": 86400,  # 24 hours in seconds
            "expires_at": expires_at.isoformat(),
        }

    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.

        Note: MVP doesn't implement refresh tokens.
        This is a placeholder for future implementation.

        Args:
            refresh_token: Refresh token string

        Returns:
            Dictionary with new access token

        Raises:
            BadRequestException: In MVP, refresh tokens not implemented
        """
        # Placeholder implementation
        # In production, would:
        # 1. Validate refresh token
        # 2. Check if token is revoked/expired
        # 3. Get user from token
        # 4. Generate new access token
        # 5. Optionally rotate refresh token

        raise BadRequestException(
            "Refresh tokens are not implemented in MVP. "
            "Please re-authenticate using OTP or OAuth."
        )

    async def validate_customer_token(
        self,
        token: str,
    ) -> User:
        """
        Validate customer JWT token and return user.

        Args:
            token: JWT access token

        Returns:
            User instance if token is valid

        Raises:
            UnauthorizedException: If token is invalid or user not found
        """
        try:
            payload = decode_access_token(token)
        except Exception as e:
            raise UnauthorizedException(f"Invalid token: {str(e)}")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid token payload")

        # Get user from database
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user or not user.is_active:
            raise UnauthorizedException("User not found or inactive")

        # Verify user is a customer
        if user.user_type != UserType.CUSTOMER:
            raise UnauthorizedException("Token is not for a customer user")

        return user