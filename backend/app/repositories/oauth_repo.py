"""
OAuth repository for database operations.

Extends BaseRepository with OAuth-specific queries for finding
connections by provider, provider_id, or user.
"""
import uuid
from typing import Optional, List

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_connection import OAuthConnection, OAuthProvider
from app.repositories.base import BaseRepository


class OAuthRepository(BaseRepository[OAuthConnection]):
    """Repository for OAuthConnection model with custom queries."""

    def __init__(self, session: AsyncSession):
        """
        Initialize OAuth repository.

        Args:
            session: Async database session
        """
        super().__init__(OAuthConnection, session)

    async def find_by_provider_and_id(
        self,
        provider: OAuthProvider,
        provider_id: str,
    ) -> Optional[OAuthConnection]:
        """
        Find OAuth connection by provider and provider ID.

        Args:
            provider: OAuth provider (google, facebook, apple, github)
            provider_id: External provider user ID

        Returns:
            OAuthConnection instance or None if not found
        """
        result = await self.session.execute(
            select(OAuthConnection).where(
                and_(
                    OAuthConnection.provider == provider,
                    OAuthConnection.provider_id == provider_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def find_by_user_and_provider(
        self,
        user_id: uuid.UUID,
        provider: OAuthProvider,
    ) -> Optional[OAuthConnection]:
        """
        Find OAuth connection by user ID and provider.

        Args:
            user_id: Local user ID
            provider: OAuth provider

        Returns:
            OAuthConnection instance or None if not found
        """
        result = await self.session.execute(
            select(OAuthConnection).where(
                and_(
                    OAuthConnection.user_id == user_id,
                    OAuthConnection.provider == provider,
                )
            )
        )
        return result.scalar_one_or_none()

    async def find_by_user_id(
        self,
        user_id: uuid.UUID,
    ) -> List[OAuthConnection]:
        """
        Find all OAuth connections for a user.

        Args:
            user_id: Local user ID

        Returns:
            List of OAuthConnection instances
        """
        result = await self.session.execute(
            select(OAuthConnection)
            .where(OAuthConnection.user_id == user_id)
            .order_by(OAuthConnection.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_by_email(
        self,
        email: str,
        provider: Optional[OAuthProvider] = None,
    ) -> List[OAuthConnection]:
        """
        Find OAuth connections by email address.

        Args:
            email: Email address from provider
            provider: Optional provider filter

        Returns:
            List of OAuthConnection instances
        """
        conditions = [OAuthConnection.email == email]
        if provider:
            conditions.append(OAuthConnection.provider == provider)

        result = await self.session.execute(
            select(OAuthConnection).where(and_(*conditions))
        )
        return list(result.scalars().all())

    async def update_tokens(
        self,
        connection_id: uuid.UUID,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional = None,
    ) -> bool:
        """
        Update OAuth connection tokens.

        Args:
            connection_id: ID of the OAuth connection
            access_token: Optional new access token
            refresh_token: Optional new refresh token
            token_expires_at: Optional new token expiration

        Returns:
            True if updated, False if not found
        """
        connection = await self.get_by_id(connection_id)
        if not connection:
            return False

        update_data = {}
        if access_token is not None:
            update_data["access_token"] = access_token
        if refresh_token is not None:
            update_data["refresh_token"] = refresh_token
        if token_expires_at is not None:
            update_data["token_expires_at"] = token_expires_at

        await self.update(connection_id, **update_data)
        return True