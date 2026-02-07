"""
User model for admin authentication and authorization, and customer accounts.

Manages admin users with role-based access control and customer accounts
for storefront authentication via OTP/OAuth.
"""
import enum
from typing import Optional
import uuid

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    """User role enumeration for access control."""
    
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    OPERATOR = "operator"


class UserType(str, enum.Enum):
    """User type enumeration (admin vs customer)."""
    
    ADMIN = "admin"
    CUSTOMER = "customer"


class User(Base, UUIDMixin, TimestampMixin):
    """
    User entity for admin authentication and customer accounts.
    
    Attributes:
        user_type: Type of user (admin or customer)
        email: Email address (unique per storefront for customers)
        phone: Phone number (unique per storefront for customers)
        hashed_password: Bcrypt hashed password (for admin users only)
        role: User role (superadmin, admin, operator) - only for admin users
        storefront_id: Foreign key to storefront (required for customers)
        first_name: User's first name
        last_name: User's last name
        is_active: Whether the user account is active
        email_verified: Whether email has been verified (customers)
        phone_verified: Whether phone has been verified (customers)
        oauth_provider: OAuth provider name (google, facebook, apple) if linked
        oauth_id: External OAuth provider user ID
    """
    
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("storefront_id", "email", name="uq_storefront_email"),
        UniqueConstraint("storefront_id", "phone", name="uq_storefront_phone"),
        CheckConstraint(
            "(user_type = 'customer' AND storefront_id IS NOT NULL) OR "
            "(user_type = 'admin' AND storefront_id IS NULL)",
            name="ck_user_type_storefront"
        ),
    )
    
    user_type: Mapped[UserType] = mapped_column(
        Enum(UserType, name="user_type", native_enum=False),
        nullable=False,
        default=UserType.ADMIN,
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
    
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    role: Mapped[Optional[UserRole]] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False),
        nullable=True,
    )
    
    storefront_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storefronts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    
    first_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    last_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    oauth_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    oauth_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Relationships
    # storefront: Mapped[Optional["Storefront"]] = relationship(
    #     "Storefront",
    #     back_populates="users",
    #     lazy="select",
    # )
    
    carts: Mapped[list["Cart"]] = relationship(
        "Cart",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    oauth_connections: Mapped[list["OAuthConnection"]] = relationship(
        "OAuthConnection",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, user_type={self.user_type})>"
