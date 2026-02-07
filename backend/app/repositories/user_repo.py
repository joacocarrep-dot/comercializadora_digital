"""
User repository for database operations.

Extends BaseRepository with user-specific queries for finding
users by email/phone, checking customer status, and storefront scoping.
"""
import uuid
from typing import Optional, List

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserType
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with custom queries."""

    def __init__(self, session: AsyncSession):
        """
        Initialize user repository.

        Args:
            session: Async database session
        """
        super().__init__(User, session)

    async def find_by_email_and_storefront(
        self,
        email: str,
        storefront_id: uuid.UUID,
        user_type: Optional[UserType] = UserType.CUSTOMER,
    ) -> Optional[User]:
        """
        Find a user by email and storefront ID.

        Args:
            email: Email address
            storefront_id: Storefront UUID
            user_type: Optional user type filter (default: customer)

        Returns:
            User instance or None if not found
        """
        conditions = [
            User.email == email,
            User.storefront_id == storefront_id,
            User.is_active == True,
        ]
        if user_type:
            conditions.append(User.user_type == user_type)

        result = await self.session.execute(
            select(User).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def find_by_phone_and_storefront(
        self,
        phone: str,
        storefront_id: uuid.UUID,
        user_type: Optional[UserType] = UserType.CUSTOMER,
    ) -> Optional[User]:
        """
        Find a user by phone and storefront ID.

        Args:
            phone: Phone number
            storefront_id: Storefront UUID
            user_type: Optional user type filter (default: customer)

        Returns:
            User instance or None if not found
        """
        conditions = [
            User.phone == phone,
            User.storefront_id == storefront_id,
            User.is_active == True,
        ]
        if user_type:
            conditions.append(User.user_type == user_type)

        result = await self.session.execute(
            select(User).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def find_by_oauth_provider_and_id(
        self,
        oauth_provider: str,
        oauth_id: str,
        storefront_id: Optional[uuid.UUID] = None,
    ) -> Optional[User]:
        """
        Find a user by OAuth provider and provider ID.

        Args:
            oauth_provider: OAuth provider name
            oauth_id: External provider user ID
            storefront_id: Optional storefront ID for scoping

        Returns:
            User instance or None if not found
        """
        conditions = [
            User.oauth_provider == oauth_provider,
            User.oauth_id == oauth_id,
            User.is_active == True,
        ]
        if storefront_id:
            conditions.append(User.storefront_id == storefront_id)

        result = await self.session.execute(
            select(User).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def find_customers_by_storefront(
        self,
        storefront_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[User]:
        """
        Find all customers for a storefront.

        Args:
            storefront_id: Storefront UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of customer User instances
        """
        result = await self.session.execute(
            select(User)
            .where(
                and_(
                    User.storefront_id == storefront_id,
                    User.user_type == UserType.CUSTOMER,
                    User.is_active == True,
                )
            )
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_customers_by_storefront(
        self,
        storefront_id: uuid.UUID,
    ) -> int:
        """
        Count active customers for a storefront.

        Args:
            storefront_id: Storefront UUID

        Returns:
            Number of active customers
        """
        result = await self.session.execute(
            select(User)
            .where(
                and_(
                    User.storefront_id == storefront_id,
                    User.user_type == UserType.CUSTOMER,
                    User.is_active == True,
                )
            )
        )
        return len(list(result.scalars().all()))