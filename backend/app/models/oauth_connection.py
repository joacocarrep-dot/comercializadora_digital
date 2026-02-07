"""
OAuth Connection model for storing external OAuth provider connections.

Stores links between local user accounts and external OAuth providers
(Google, Facebook, Apple, etc.) to allow social login.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class OAuthProvider(str, enum.Enum):
    """Supported OAuth providers."""
    
    GOOGLE = "google"
    FACEBOOK = "facebook"
    APPLE = "apple"
    GITHUB = "github"


class OAuthConnection(Base, UUIDMixin, TimestampMixin):
    """
    OAuth Connection entity for storing external provider links.
    
    Attributes:
        user_id: Foreign key to local user
        provider: OAuth provider name (google, facebook, apple, github)
        provider_id: Unique user identifier from the provider
        email: Email address from provider (may differ from user.email)
        display_name: Display name from provider
        profile_picture: URL to profile picture from provider
        access_token: Encrypted access token (optional, for future use)
        refresh_token: Encrypted refresh token (optional, for future use)
        token_expires_at: When the access token expires (optional)
        profile_data: Raw JSON profile data from provider for debugging
    """
    
    __tablename__ = "oauth_connections"
    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_provider_provider_id"),
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    provider: Mapped[OAuthProvider] = mapped_column(
        Enum(OAuthProvider, name="oauth_provider", native_enum=False),
        nullable=False,
        index=True,
    )
    
    provider_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    
    display_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    profile_picture: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    access_token: Mapped[Optional[str]] = mapped_column(
        String(2000),  # Encrypted token can be long
        nullable=True,
    )
    
    refresh_token: Mapped[Optional[str]] = mapped_column(
        String(2000),  # Encrypted token can be long
        nullable=True,
    )
    
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    profile_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="oauth_connections",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<OAuthConnection(id={self.id}, user_id={self.user_id}, provider={self.provider})>"