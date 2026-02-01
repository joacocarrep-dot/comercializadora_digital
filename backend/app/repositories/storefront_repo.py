"""
Storefront repository for database operations.

Extends BaseRepository with storefront-specific queries including
API key verification for authentication.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storefront import Storefront
from app.repositories.base import BaseRepository


class StorefrontRepository(BaseRepository[Storefront]):
    """Repository for Storefront model with custom queries."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize storefront repository.
        
        Args:
            session: Async database session
        """
        super().__init__(Storefront, session)
    
    async def get_by_code(self, code: str) -> Optional[Storefront]:
        """
        Get a storefront by unique code.
        
        Args:
            code: Storefront code
            
        Returns:
            Storefront instance or None if not found
        """
        result = await self.session.execute(
            select(Storefront).where(Storefront.code == code)
        )
        return result.scalar_one_or_none()
    
    async def get_by_api_key_hash(self, api_key_hash: str) -> Optional[Storefront]:
        """
        Get a storefront by API key hash.
        
        Used for authentication middleware to verify API keys.
        
        Args:
            api_key_hash: Hashed API key
            
        Returns:
            Storefront instance or None if not found
        """
        result = await self.session.execute(
            select(Storefront).where(Storefront.api_key_hash == api_key_hash)
        )
        return result.scalar_one_or_none()
    
    async def get_active_storefronts(self, skip: int = 0, limit: int = 100):
        """
        Get all active storefronts.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of active storefront instances
        """
        return await self.get_all(skip=skip, limit=limit, filters={"is_active": True})
