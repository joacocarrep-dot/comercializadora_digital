"""
Cart repository for database operations.

Extends BaseRepository with cart-specific queries for finding carts
by user_id, anonymous_id, or both.
"""
import uuid
from typing import Optional, Tuple

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy.orm

from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.repositories.base import BaseRepository


class CartRepository(BaseRepository[Cart]):
    """Repository for Cart model with custom queries."""

    def __init__(self, session: AsyncSession):
        """
        Initialize cart repository.

        Args:
            session: Async database session
        """
        super().__init__(Cart, session)

    async def get_by_user_id(
        self, storefront_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Cart]:
        """
        Get a cart by storefront ID and user ID.

        Args:
            storefront_id: ID of the storefront
            user_id: ID of the user

        Returns:
            Cart instance or None if not found
        """
        result = await self.session.execute(
            select(Cart).where(
                and_(
                    Cart.storefront_id == storefront_id,
                    Cart.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_anonymous_id(
        self, storefront_id: uuid.UUID, anonymous_id: str
    ) -> Optional[Cart]:
        """
        Get a cart by storefront ID and anonymous ID.

        Args:
            storefront_id: ID of the storefront
            anonymous_id: Anonymous identifier string

        Returns:
            Cart instance or None if not found
        """
        result = await self.session.execute(
            select(Cart).where(
                and_(
                    Cart.storefront_id == storefront_id,
                    Cart.anonymous_id == anonymous_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_or_anonymous(
        self,
        storefront_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        anonymous_id: Optional[str] = None,
    ) -> Optional[Cart]:
        """
        Get a cart by storefront ID and either user_id or anonymous_id.

        Args:
            storefront_id: ID of the storefront
            user_id: Optional user ID
            anonymous_id: Optional anonymous identifier

        Returns:
            Cart instance or None if not found

        Raises:
            ValueError: If neither user_id nor anonymous_id is provided
        """
        if not user_id and not anonymous_id:
            raise ValueError("Either user_id or anonymous_id must be provided")

        conditions = [Cart.storefront_id == storefront_id]
        user_or_anonymous_conditions = []

        if user_id:
            user_or_anonymous_conditions.append(Cart.user_id == user_id)
        if anonymous_id:
            user_or_anonymous_conditions.append(Cart.anonymous_id == anonymous_id)

        # Combine user/anonymous conditions with OR if both provided
        if len(user_or_anonymous_conditions) == 1:
            conditions.append(user_or_anonymous_conditions[0])
        elif len(user_or_anonymous_conditions) > 1:
            conditions.append(or_(*user_or_anonymous_conditions))

        result = await self.session.execute(select(Cart).where(and_(*conditions)))
        return result.scalar_one_or_none()

    async def get_cart_with_items(self, cart_id: uuid.UUID) -> Optional[Cart]:
        """
        Get a cart with its items preloaded.

        Args:
            cart_id: ID of the cart

        Returns:
            Cart instance with cart_items relationship loaded, or None if not found
        """
        result = await self.session.execute(
            select(Cart)
            .where(Cart.id == cart_id)
            .options(sqlalchemy.orm.selectinload(Cart.cart_items))
        )
        return result.scalar_one_or_none()

    async def get_cart_item_by_product_variant(
        self, cart_id: uuid.UUID, product_id: uuid.UUID, variant_id: Optional[uuid.UUID] = None
    ) -> Optional[CartItem]:
        """
        Get a cart item by cart ID, product ID, and optional variant ID.

        Args:
            cart_id: ID of the cart
            product_id: ID of the product
            variant_id: Optional ID of the product variant

        Returns:
            CartItem instance or None if not found
        """
        conditions = [
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id,
        ]

        if variant_id:
            conditions.append(CartItem.variant_id == variant_id)
        else:
            conditions.append(CartItem.variant_id.is_(None))

        result = await self.session.execute(
            select(CartItem).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def get_user_carts_by_contact_email(
        self, storefront_id: uuid.UUID, contact_email: str
    ) -> list[Cart]:
        """
        Get carts by storefront ID and contact email (for guest checkout lookup).

        Args:
            storefront_id: ID of the storefront
            contact_email: Contact email address

        Returns:
            List of Cart instances matching the criteria
        """
        result = await self.session.execute(
            select(Cart).where(
                and_(
                    Cart.storefront_id == storefront_id,
                    Cart.contact_email == contact_email,
                )
            )
        )
        return list(result.scalars().all())