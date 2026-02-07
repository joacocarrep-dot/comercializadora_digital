"""
OTP Code model for storing one-time passwords for customer authentication.

Stores verification codes sent via email or SMS with expiration tracking
and usage status.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class OTPPurpose(str, enum.Enum):
    """Purpose of the OTP code."""
    
    LOGIN = "login"
    VERIFY_EMAIL = "verify_email"
    VERIFY_PHONE = "verify_phone"
    RESET_PASSWORD = "reset_password"


class OTPCode(Base, UUIDMixin, TimestampMixin):
    """
    OTP Code entity for storing verification codes.
    
    Attributes:
        email: Email address to which the code was sent (nullable if phone used)
        phone: Phone number to which the code was sent (nullable if email used)
        code: 6-digit verification code
        purpose: Purpose of the code (login, verify_email, verify_phone, reset_password)
        expires_at: Timestamp when the code expires
        used: Whether the code has been used
        used_at: Timestamp when the code was used (nullable)
        user_id: Foreign key to user (nullable, linked after verification)
        storefront_id: Foreign key to storefront (required for customer OTPs)
    """
    
    __tablename__ = "otp_codes"
    __table_args__ = (
        UniqueConstraint("email", "code", "purpose", name="uq_email_code_purpose"),
        UniqueConstraint("phone", "code", "purpose", name="uq_phone_code_purpose"),
        Index("ix_otp_codes_email_expires", "email", "expires_at"),
        Index("ix_otp_codes_phone_expires", "phone", "expires_at"),
        Index("ix_otp_codes_expires_at", "expires_at"),
    )
    
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    
    code: Mapped[str] = mapped_column(
        String(6),
        nullable=False,
    )
    
    purpose: Mapped[OTPPurpose] = mapped_column(
        Enum(OTPPurpose, name="otp_purpose", native_enum=False),
        nullable=False,
        default=OTPPurpose.LOGIN,
    )
    
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    
    used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    
    storefront_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storefronts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates=None,  # User doesn't have back_populates for OTP codes
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<OTPCode(id={self.id}, email={self.email}, phone={self.phone}, used={self.used})>"