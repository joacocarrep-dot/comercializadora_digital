"""
Supplier repository for database operations.

Extends BaseRepository with supplier-specific queries.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    """Repository for Supplier model with custom queries."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize supplier repository.
        
        Args:
            session: Async database session
        """
        super().__init__(Supplier, session)
    
    async def get_by_code(self, code: str) -> Optional[Supplier]:
        """
        Get a supplier by unique code.
        
        Args:
            code: Supplier code
            
        Returns:
            Supplier instance or None if not found
        """
        result = await self.session.execute(
            select(Supplier).where(Supplier.code == code)
        )
        return result.scalar_one_or_none()
    
    async def get_active_suppliers(self, skip: int = 0, limit: int = 100):
        """
        Get all active suppliers.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of active supplier instances
        """
        return await self.get_all(skip=skip, limit=limit, filters={"is_active": True})
