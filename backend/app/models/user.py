"""
User model for admin authentication and authorization.

Manages admin users with role-based access control and optional
storefront association for scoped permissions.
"""
import enum
from typing import Optional
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    """User role enumeration for access control."""
    
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    OPERATOR = "operator"


class User(Base, UUIDMixin, TimestampMixin):
    """
    User entity for admin authentication and authorization.
    
    Attributes:
        email: Unique email address for login
        hashed_password: Bcrypt hashed password
        role: User role (superadmin, admin, operator)
        storefront_id: Optional FK to storefront for scoped access
        first_name: User's first name
        last_name: User's last name
        is_active: Whether the user account is active
    """
    
    __tablename__ = "users"
    
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False),
        nullable=False,
        default=UserRole.OPERATOR,
    )
    
    storefront_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storefronts.id", ondelete="SET NULL"),
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
    
    # Relationship to storefront (lazy loaded)
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
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
