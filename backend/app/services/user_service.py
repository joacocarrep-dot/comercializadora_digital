"""
User service for customer account management.

Handles customer creation, retrieval, and profile updates
for storefront authentication.
"""
import uuid
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.user import User, UserType
from app.repositories.user_repo import UserRepository
from app.repositories.base import BaseRepository


class UserService:
    """
    Service for user business logic operations.

    Attributes:
        session: Async database session
        user_repo: UserRepository for User model operations
        base_user_repo: BaseRepository for generic User operations
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize user service with database session.

        Args:
            session: Async database session
        """
        self.session = session
        self.user_repo = UserRepository(session)
        self.base_user_repo = BaseRepository(User, session)

    async def create_user(
        self,
        storefront_id: uuid.UUID,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email_verified: bool = False,
        phone_verified: bool = False,
        oauth_provider: Optional[str] = None,
        oauth_id: Optional[str] = None,
    ) -> User:
        """
        Create a new customer user.

        Validates uniqueness constraints per storefront for email/phone.
        Customers cannot have passwords (hashed_password must be NULL).

        Args:
            email: Email address (optional if phone provided)
            phone: Phone number (optional if email provided)
            storefront_id: Storefront UUID (required for customers)
            first_name: Optional first name
            last_name: Optional last name
            email_verified: Whether email is verified (default: False)
            phone_verified: Whether phone is verified (default: False)
            oauth_provider: Optional OAuth provider name
            oauth_id: Optional external OAuth provider user ID

        Returns:
            Created User instance

        Raises:
            BadRequestException: If neither email nor phone provided
            ConflictException: If email or phone already exists for storefront
        """
        if not email and not phone:
            raise BadRequestException("Either email or phone must be provided")

        # Check uniqueness constraints
        if email:
            existing = await self.user_repo.find_by_email_and_storefront(
                storefront_id=storefront_id,
                user_type=UserType.CUSTOMER,
                email=email,
            )
            if existing:
                raise ConflictException(
                    f"Email '{email}' already exists for this storefront"
                )

        if phone:
            existing = await self.user_repo.find_by_phone_and_storefront(
                phone=phone,
                storefront_id=storefront_id,
                user_type=UserType.CUSTOMER,
            )
            if existing:
                raise ConflictException(
                    f"Phone '{phone}' already exists for this storefront"
                )

        # Check OAuth uniqueness if provided
        if oauth_provider and oauth_id:
            existing = await self.user_repo.find_by_oauth_provider_and_id(
                oauth_provider=oauth_provider,
                oauth_id=oauth_id,
                storefront_id=storefront_id,
            )
            if existing:
                raise ConflictException(
                    f"OAuth account {oauth_provider}:{oauth_id} already linked"
                )

        # Create user
        user_data = {
            "user_type": UserType.CUSTOMER,
            "email": email,
            "phone": phone,
            "hashed_password": None,  # Customers don't have passwords
            "role": None,  # Customers don't have admin roles
            "storefront_id": storefront_id,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
            "email_verified": email_verified,
            "phone_verified": phone_verified,
            "oauth_provider": oauth_provider,
            "oauth_id": oauth_id,
        }

        return await self.base_user_repo.create(**user_data)

    async def get_or_create_by_email(
        self,
        email: str,
        storefront_id: uuid.UUID,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email_verified: bool = True,
        create_if_not_exists: bool = True,
    ) -> User:
        """
        Get existing user by email or create new one.

        Args:
            email: Email address
            storefront_id: Storefront UUID
            first_name: Optional first name for new users
            last_name: Optional last name for new users
            email_verified: Whether email is verified (default: True)
            create_if_not_exists: Whether to create user if not found

        Returns:
            Existing or newly created User instance

        Raises:
            NotFoundException: If user not found and create_if_not_exists=False
            ConflictException: If email exists but not for this storefront
        """
        # Try to find existing user
        user = await self.user_repo.find_by_email_and_storefront(
            email=email,
            storefront_id=storefront_id,
            user_type=UserType.CUSTOMER,
        )

        if user:
            # Update verification status if needed
            if email_verified and not user.email_verified:
                user.email_verified = True
                await self.session.commit()
                await self.session.refresh(user)
            return user

        # User not found
        if not create_if_not_exists:
            raise NotFoundException("User", f"email={email}, storefront={storefront_id}")

        # Check if email exists in another storefront
        query = """
            SELECT EXISTS(
                SELECT 1 FROM users 
                WHERE email = :email 
                AND user_type = 'customer' 
                AND is_active = true
            )
        """
        result = await self.session.execute(
            query, {"email": email}
        )
        email_exists_elsewhere = result.scalar()

        if email_exists_elsewhere:
            # Email exists but for different storefront - this is allowed
            # Users are independent per storefront
            pass

        # Create new user
        return await self.create_user(
            email=email,
            storefront_id=storefront_id,
            first_name=first_name,
            last_name=last_name,
            email_verified=email_verified,
            phone_verified=False,
        )

    async def update_profile(
        self,
        user_id: uuid.UUID,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> User:
        """
        Update user profile information.

        Args:
            user_id: User UUID
            first_name: Optional new first name
            last_name: Optional new last name
            email: Optional new email (must be verified through OTP)
            phone: Optional new phone (must be verified through OTP)

        Returns:
            Updated User instance

        Raises:
            NotFoundException: If user not found
            ConflictException: If email or phone already exists for storefront
            BadRequestException: If trying to update email/phone without verification
        """
        user = await self.base_user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        update_data = {}

        # Update basic profile fields
        if first_name is not None:
            update_data["first_name"] = first_name
        if last_name is not None:
            update_data["last_name"] = last_name

        # Email update requires verification
        if email is not None and email != user.email:
            if not user.email_verified:
                # Allow email change only if current email is verified
                # or we're setting it for the first time
                if user.email:
                    raise BadRequestException(
                        "Current email must be verified before changing to a new email"
                    )

            # Check uniqueness
            existing = await self.user_repo.find_by_email_and_storefront(
                email=email,
                storefront_id=user.storefront_id,
                user_type=UserType.CUSTOMER,
            )
            if existing and existing.id != user_id:
                raise ConflictException(
                    f"Email '{email}' already exists for this storefront"
                )

            update_data["email"] = email
            update_data["email_verified"] = False  # New email requires verification

        # Phone update requires verification
        if phone is not None and phone != user.phone:
            if not user.phone_verified:
                # Allow phone change only if current phone is verified
                # or we're setting it for the first time
                if user.phone:
                    raise BadRequestException(
                        "Current phone must be verified before changing to a new phone"
                    )

            # Check uniqueness
            existing = await self.user_repo.find_by_phone_and_storefront(
                phone=phone,
                storefront_id=user.storefront_id,
                user_type=UserType.CUSTOMER,
            )
            if existing and existing.id != user_id:
                raise ConflictException(
                    f"Phone '{phone}' already exists for this storefront"
                )

            update_data["phone"] = phone
            update_data["phone_verified"] = False  # New phone requires verification

        if not update_data:
            return user  # No changes

        updated_user = await self.base_user_repo.update(user_id, **update_data)
        if not updated_user:
            raise NotFoundException("User", user_id)

        return updated_user

    async def verify_email(
        self,
        user_id: uuid.UUID,
    ) -> User:
        """
        Mark user's email as verified.

        Args:
            user_id: User UUID

        Returns:
            Updated User instance

        Raises:
            NotFoundException: If user not found
            BadRequestException: If user has no email
        """
        user = await self.base_user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        if not user.email:
            raise BadRequestException("User does not have an email to verify")

        if user.email_verified:
            return user  # Already verified

        updated_user = await self.base_user_repo.update(
            user_id, email_verified=True
        )
        if not updated_user:
            raise NotFoundException("User", user_id)

        return updated_user

    async def verify_phone(
        self,
        user_id: uuid.UUID,
    ) -> User:
        """
        Mark user's phone as verified.

        Args:
            user_id: User UUID

        Returns:
            Updated User instance

        Raises:
            NotFoundException: If user not found
            BadRequestException: If user has no phone
        """
        user = await self.base_user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        if not user.phone:
            raise BadRequestException("User does not have a phone to verify")

        if user.phone_verified:
            return user  # Already verified

        updated_user = await self.base_user_repo.update(
            user_id, phone_verified=True
        )
        if not updated_user:
            raise NotFoundException("User", user_id)

        return updated_user

    async def link_oauth_account(
        self,
        user_id: uuid.UUID,
        oauth_provider: str,
        oauth_id: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        """
        Link OAuth account to existing user.

        Args:
            user_id: User UUID
            oauth_provider: OAuth provider name
            oauth_id: External provider user ID
            email: Optional email from OAuth provider
            first_name: Optional first name from OAuth provider
            last_name: Optional last name from OAuth provider

        Returns:
            Updated User instance

        Raises:
            NotFoundException: If user not found
            ConflictException: If OAuth account already linked to another user
        """
        user = await self.base_user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        # Check if OAuth account already linked to another user
        existing = await self.user_repo.find_by_oauth_provider_and_id(
            oauth_provider=oauth_provider,
            oauth_id=oauth_id,
            storefront_id=user.storefront_id,
        )
        if existing and existing.id != user_id:
            raise ConflictException(
                f"OAuth account {oauth_provider}:{oauth_id} already linked to another user"
            )

        update_data = {
            "oauth_provider": oauth_provider,
            "oauth_id": oauth_id,
        }

        # Update email if provided and not set
        if email and not user.email:
            update_data["email"] = email
            update_data["email_verified"] = True  # OAuth emails are considered verified

        # Update name if provided and not set
        if first_name and not user.first_name:
            update_data["first_name"] = first_name
        if last_name and not user.last_name:
            update_data["last_name"] = last_name

        updated_user = await self.base_user_repo.update(user_id, **update_data)
        if not updated_user:
            raise NotFoundException("User", user_id)

        return updated_user