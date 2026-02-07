"""
OTP repository for database operations.

Extends BaseRepository with OTP-specific queries for finding
valid codes by email/phone, checking expiration, and cleanup.
"""
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.otp_code import OTPCode, OTPPurpose
from app.repositories.base import BaseRepository


class OTPRepository(BaseRepository[OTPCode]):
    """Repository for OTPCode model with custom queries."""

    def __init__(self, session: AsyncSession):
        """
        Initialize OTP repository.

        Args:
            session: Async database session
        """
        super().__init__(OTPCode, session)

    async def find_valid_code(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        code: str = "",
        purpose: OTPPurpose = OTPPurpose.LOGIN,
        storefront_id: Optional[uuid.UUID] = None,
    ) -> Optional[OTPCode]:
        """
        Find a valid (non-expired, unused) OTP code.

        Args:
            email: Email address (optional if phone provided)
            phone: Phone number (optional if email provided)
            code: 6-digit verification code
            purpose: Purpose of the OTP code
            storefront_id: Optional storefront ID for scoping

        Returns:
            OTPCode instance or None if not found or invalid
        """
        if not email and not phone:
            raise ValueError("Either email or phone must be provided")

        now = datetime.utcnow()
        conditions = [
            OTPCode.code == code,
            OTPCode.purpose == purpose,
            OTPCode.used == False,
            OTPCode.expires_at > now,
        ]

        if email:
            conditions.append(OTPCode.email == email)
        if phone:
            conditions.append(OTPCode.phone == phone)
        if storefront_id:
            conditions.append(OTPCode.storefront_id == storefront_id)

        result = await self.session.execute(
            select(OTPCode).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def find_recent_codes(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        purpose: Optional[OTPPurpose] = None,
        limit: int = 5,
        storefront_id: Optional[uuid.UUID] = None,
    ) -> List[OTPCode]:
        """
        Find recent OTP codes for a contact, ordered by creation time.

        Args:
            email: Email address (optional if phone provided)
            phone: Phone number (optional if email provided)
            purpose: Optional purpose filter
            limit: Maximum number of codes to return
            storefront_id: Optional storefront ID for scoping

        Returns:
            List of recent OTPCode instances
        """
        if not email and not phone:
            raise ValueError("Either email or phone must be provided")

        conditions = []
        if email:
            conditions.append(OTPCode.email == email)
        if phone:
            conditions.append(OTPCode.phone == phone)
        if purpose:
            conditions.append(OTPCode.purpose == purpose)
        if storefront_id:
            conditions.append(OTPCode.storefront_id == storefront_id)

        query = (
            select(OTPCode)
            .where(and_(*conditions))
            .order_by(OTPCode.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def mark_code_as_used(self, code_id: uuid.UUID) -> bool:
        """
        Mark an OTP code as used.

        Args:
            code_id: ID of the OTP code

        Returns:
            True if updated, False if not found
        """
        code = await self.get_by_id(code_id)
        if not code:
            return False

        code.used = True
        code.used_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(code)
        return True

    async def cleanup_expired_codes(
        self, older_than: Optional[datetime] = None
    ) -> int:
        """
        Delete expired OTP codes.

        Args:
            older_than: Optional cutoff date (default: all expired codes)

        Returns:
            Number of codes deleted
        """
        now = datetime.utcnow()
        cutoff = older_than if older_than else now

        query = select(OTPCode).where(
            or_(
                OTPCode.expires_at <= cutoff,
                and_(OTPCode.used == True, OTPCode.used_at <= cutoff),
            )
        )
        result = await self.session.execute(query)
        codes = list(result.scalars().all())

        for code in codes:
            await self.session.delete(code)

        await self.session.commit()
        return len(codes)

    async def get_active_codes_count(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        storefront_id: Optional[uuid.UUID] = None,
    ) -> int:
        """
        Count active (non-expired, unused) OTP codes for a contact.

        Args:
            email: Email address (optional if phone provided)
            phone: Phone number (optional if email provided)
            storefront_id: Optional storefront ID for scoping

        Returns:
            Number of active codes
        """
        if not email and not phone:
            raise ValueError("Either email or phone must be provided")

        now = datetime.utcnow()
        conditions = [
            OTPCode.used == False,
            OTPCode.expires_at > now,
        ]

        if email:
            conditions.append(OTPCode.email == email)
        if phone:
            conditions.append(OTPCode.phone == phone)
        if storefront_id:
            conditions.append(OTPCode.storefront_id == storefront_id)

        query = select(OTPCode).where(and_(*conditions))
        result = await self.session.execute(query)
        return len(list(result.scalars().all()))