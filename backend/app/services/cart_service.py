"""
Cart service for business logic related to shopping carts.

Handles cart creation, item management, cart merging for anonymous users,
and price validation. Supports both authenticated users and anonymous shoppers.
"""
import uuid
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    ForbiddenException,
)
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.storefront_product import StorefrontProduct
from app.models.storefront import Storefront
from app.models.inventory import Inventory
from app.repositories.base import BaseRepository
from app.repositories.cart_repo import CartRepository


class CartService:
    """
    Service for cart business logic operations.

    Attributes:
        session: Async database session
        cart_repo: CartRepository for Cart model operations
        cart_item_repo: BaseRepository for CartItem model
        product_repo: BaseRepository for Product model
        product_variant_repo: BaseRepository for ProductVariant model
        storefront_product_repo: BaseRepository for StorefrontProduct model
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize cart service with database session.

        Args:
            session: Async database session
        """
        self.session = session
        self.cart_repo = CartRepository(session)
        self.cart_item_repo = BaseRepository(CartItem, session)
        self.product_repo = BaseRepository(Product, session)
        self.product_variant_repo = BaseRepository(ProductVariant, session)
        self.storefront_product_repo = BaseRepository(StorefrontProduct, session)

    async def get_or_create_cart(
        self,
        storefront_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        anonymous_id: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
    ) -> Cart:
        """
        Get an existing cart or create a new one.

        Looks for cart by user_id (if authenticated) or anonymous_id (if guest).
        If neither user_id nor anonymous_id is provided, raises BadRequestException.

        Args:
            storefront_id: ID of the storefront
            user_id: Optional user ID (for authenticated users)
            anonymous_id: Optional anonymous identifier (for guest users)
            contact_email: Optional contact email for guest checkout
            contact_phone: Optional contact phone for guest checkout

        Returns:
            Existing or newly created Cart instance

        Raises:
            BadRequestException: If neither user_id nor anonymous_id is provided
            NotFoundException: If storefront not found
        """
        if not user_id and not anonymous_id:
            raise BadRequestException(
                "Either user_id or anonymous_id must be provided to identify cart"
            )

        # Verify storefront exists
        storefront = await self.session.get(Storefront, storefront_id)
        if not storefront:
            raise NotFoundException("Storefront", storefront_id)

        # Try to find existing cart
        cart = await self.cart_repo.get_by_user_or_anonymous(
            storefront_id=storefront_id,
            user_id=user_id,
            anonymous_id=anonymous_id,
        )

        if cart:
            # Update contact info if provided and cart belongs to current user
            update_data = {}
            if contact_email and not cart.user_id:  # Only update for anonymous carts
                update_data["contact_email"] = contact_email
            if contact_phone and not cart.user_id:
                update_data["contact_phone"] = contact_phone

            if update_data:
                await self.cart_repo.update(cart.id, **update_data)
                await self.session.refresh(cart)

            return cart

        # Create new cart
        cart_data = {
            "storefront_id": storefront_id,
            "user_id": user_id,
            "anonymous_id": anonymous_id,
            "contact_email": contact_email if not user_id else None,
            "contact_phone": contact_phone if not user_id else None,
            "cart_metadata": {},
        }

        # Remove None values to avoid constraint violations
        cart_data = {k: v for k, v in cart_data.items() if v is not None}

        new_cart = await self.cart_repo.create(**cart_data)
        return new_cart

    async def add_item(
        self,
        cart_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: int = 1,
        variant_id: Optional[uuid.UUID] = None,
    ) -> CartItem:
        """
        Add an item to the cart or increment quantity if already exists.

        Validates product existence, activity, and storefront assignment.
        Saves current price as price_at_addition for later comparison.

        Args:
            cart_id: ID of the cart
            product_id: ID of the product to add
            quantity: Quantity to add (default: 1)
            variant_id: Optional variant ID

        Returns:
            Created or updated CartItem instance

        Raises:
            NotFoundException: If cart, product, or variant not found
            BadRequestException: If product is not active or not assigned to storefront,
                                or if quantity is not positive
            ForbiddenException: If variant does not belong to product
        """
        if quantity <= 0:
            raise BadRequestException("Quantity must be positive")

        # Get cart with storefront info
        cart = await self.cart_repo.get_by_id(cart_id)
        if not cart:
            raise NotFoundException("Cart", cart_id)

        # Get product and validate
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundException("Product", product_id)

        if not product.is_active:
            raise BadRequestException(f"Product {product_id} is not active")

        # Validate variant if provided
        variant = None
        if variant_id:
            variant = await self.product_variant_repo.get_by_id(variant_id)
            if not variant:
                raise NotFoundException("ProductVariant", variant_id)

            if variant.product_id != product_id:
                raise ForbiddenException(
                    f"Variant {variant_id} does not belong to product {product_id}"
                )

            if not variant.is_active:
                raise BadRequestException(f"Variant {variant_id} is not active")

        # Check if product is assigned to cart's storefront
        storefront_product = await self._get_storefront_product_assignment(
            cart.storefront_id, product_id
        )
        if not storefront_product or not storefront_product.is_active:
            raise BadRequestException(
                f"Product {product_id} is not assigned to storefront {cart.storefront_id}"
            )

        # Calculate current price
        current_price = await self._get_current_product_price(
            product_id, variant_id, cart.storefront_id
        )

        # Check if item already exists in cart
        existing_item = await self.cart_repo.get_cart_item_by_product_variant(
            cart_id=cart_id, product_id=product_id, variant_id=variant_id
        )

        if existing_item:
            # Update quantity
            new_quantity = existing_item.quantity + quantity
            updated_item = await self.cart_item_repo.update(
                existing_item.id, quantity=new_quantity
            )
            if not updated_item:
                raise NotFoundException("CartItem", existing_item.id)
            return updated_item
        else:
            # Create new cart item
            item_data = {
                "cart_id": cart_id,
                "product_id": product_id,
                "variant_id": variant_id,
                "quantity": quantity,
                "price_at_addition": current_price,
            }
            return await self.cart_item_repo.create(**item_data)

    async def update_item_quantity(
        self, cart_id: uuid.UUID, item_id: uuid.UUID, quantity: int
    ) -> CartItem:
        """
        Update quantity of a cart item.

        Validates that item belongs to the cart and quantity is positive.

        Args:
            cart_id: ID of the cart
            item_id: ID of the cart item
            quantity: New quantity

        Returns:
            Updated CartItem instance

        Raises:
            NotFoundException: If cart or item not found
            BadRequestException: If quantity is not positive or item doesn't belong to cart
        """
        if quantity <= 0:
            raise BadRequestException("Quantity must be positive")

        # Verify cart exists
        cart = await self.cart_repo.get_by_id(cart_id)
        if not cart:
            raise NotFoundException("Cart", cart_id)

        # Verify item exists and belongs to cart
        item = await self.cart_item_repo.get_by_id(item_id)
        if not item:
            raise NotFoundException("CartItem", item_id)

        if item.cart_id != cart_id:
            raise BadRequestException(
                f"CartItem {item_id} does not belong to cart {cart_id}"
            )

        # Update quantity
        updated_item = await self.cart_item_repo.update(item_id, quantity=quantity)
        if not updated_item:
            raise NotFoundException("CartItem", item_id)

        return updated_item

    async def remove_item(self, cart_id: uuid.UUID, item_id: uuid.UUID) -> bool:
        """
        Remove an item from the cart.

        Validates that item belongs to the cart.

        Args:
            cart_id: ID of the cart
            item_id: ID of the cart item to remove

        Returns:
            True if item was deleted, False if not found

        Raises:
            BadRequestException: If item doesn't belong to cart
        """
        # Verify item exists and belongs to cart
        item = await self.cart_item_repo.get_by_id(item_id)
        if not item:
            return False

        if item.cart_id != cart_id:
            raise BadRequestException(
                f"CartItem {item_id} does not belong to cart {cart_id}"
            )

        # Delete item
        return await self.cart_item_repo.delete(item_id)

    async def clear_cart(self, cart_id: uuid.UUID) -> bool:
        """
        Remove all items from the cart.

        Args:
            cart_id: ID of the cart to clear

        Returns:
            True if cart was cleared, False if cart not found

        Raises:
            NotFoundException: If cart not found
        """
        # Verify cart exists
        cart = await self.cart_repo.get_by_id(cart_id)
        if not cart:
            raise NotFoundException("Cart", cart_id)

        # Delete all cart items
        query = select(CartItem).where(CartItem.cart_id == cart_id)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        for item in items:
            await self.session.delete(item)

        await self.session.commit()
        return True

    async def merge_carts(
        self, anonymous_cart_id: uuid.UUID, user_cart_id: uuid.UUID
    ) -> Cart:
        """
        Merge an anonymous cart into a user cart upon login.

        Transfers items from anonymous cart to user cart, summing quantities
        for duplicate items. Deletes the anonymous cart after successful merge.

        Args:
            anonymous_cart_id: ID of the anonymous cart
            user_cart_id: ID of the user cart

        Returns:
            Merged Cart instance (user cart)

        Raises:
            NotFoundException: If either cart not found
            BadRequestException: If carts don't belong to same storefront,
                                or if anonymous cart has user_id,
                                or if user cart has anonymous_id
        """
        # Get both carts with items preloaded
        anonymous_cart = await self.cart_repo.get_cart_with_items(anonymous_cart_id)
        user_cart = await self.cart_repo.get_cart_with_items(user_cart_id)

        if not anonymous_cart:
            raise NotFoundException("Cart", anonymous_cart_id)
        if not user_cart:
            raise NotFoundException("Cart", user_cart_id)

        # Validate cart types
        if anonymous_cart.user_id is not None:
            raise BadRequestException(
                f"Cart {anonymous_cart_id} is not an anonymous cart (has user_id)"
            )
        if user_cart.anonymous_id is not None:
            raise BadRequestException(
                f"Cart {user_cart_id} is not a user cart (has anonymous_id)"
            )

        # Ensure both carts belong to same storefront
        if anonymous_cart.storefront_id != user_cart.storefront_id:
            raise BadRequestException(
                f"Cannot merge carts from different storefronts: "
                f"{anonymous_cart.storefront_id} != {user_cart.storefront_id}"
            )

        # Merge items
        for anonymous_item in anonymous_cart.cart_items:
            # Find matching item in user cart
            matching_item = await self.cart_repo.get_cart_item_by_product_variant(
                cart_id=user_cart_id,
                product_id=anonymous_item.product_id,
                variant_id=anonymous_item.variant_id,
            )

            if matching_item:
                # Sum quantities, keep the lower price_at_addition (older price)
                new_quantity = matching_item.quantity + anonymous_item.quantity
                price_to_keep = min(
                    matching_item.price_at_addition, anonymous_item.price_at_addition
                )

                await self.cart_item_repo.update(
                    matching_item.id,
                    quantity=new_quantity,
                    price_at_addition=price_to_keep,
                )
            else:
                # Create new item in user cart
                item_data = {
                    "cart_id": user_cart_id,
                    "product_id": anonymous_item.product_id,
                    "variant_id": anonymous_item.variant_id,
                    "quantity": anonymous_item.quantity,
                    "price_at_addition": anonymous_item.price_at_addition,
                }
                await self.cart_item_repo.create(**item_data)

        # Delete anonymous cart (cascade will delete its items)
        await self.cart_repo.delete(anonymous_cart_id)

        # Return updated user cart
        updated_user_cart = await self.cart_repo.get_cart_with_items(user_cart_id)
        if not updated_user_cart:
            raise NotFoundException("Cart", user_cart_id)

        return updated_user_cart

    async def validate_cart(self, cart_id: uuid.UUID) -> Dict[str, Any]:
        """
        Validate cart items against current prices and availability.

        Compares price_at_addition with current prices and checks stock
        availability. Returns items with price changes and out-of-stock items.

        Args:
            cart_id: ID of the cart to validate

        Returns:
            Dictionary with validation results:
            {
                "cart_id": str,
                "items_with_price_changes": List[Dict],
                "items_out_of_stock": List[Dict],
                "total_price_difference": Decimal,
                "is_valid": bool
            }

        Raises:
            NotFoundException: If cart not found
        """
        cart = await self.cart_repo.get_cart_with_items(cart_id)
        if not cart:
            raise NotFoundException("Cart", cart_id)

        items_with_price_changes = []
        items_out_of_stock = []
        total_price_difference = Decimal("0.00")

        for item in cart.cart_items:
            # Get current price
            current_price = await self._get_current_product_price(
                item.product_id, item.variant_id, cart.storefront_id
            )

            # Check price change
            if current_price != item.price_at_addition:
                price_diff = current_price - item.price_at_addition
                total_price_item_diff = price_diff * item.quantity
                total_price_difference += total_price_item_diff

                items_with_price_changes.append(
                    {
                        "cart_item_id": str(item.id),
                        "product_id": str(item.product_id),
                        "variant_id": str(item.variant_id) if item.variant_id else None,
                        "old_price": float(item.price_at_addition),
                        "new_price": float(current_price),
                        "quantity": item.quantity,
                        "price_difference": float(price_diff),
                        "total_price_difference": float(total_price_item_diff),
                    }
                )

            # Check stock availability (optional, for informational purposes)
            # This doesn't block the cart, just informs the user
            stock_info = await self._get_product_stock_info(
                item.product_id, item.variant_id
            )
            if stock_info["available_qty"] < item.quantity:
                items_out_of_stock.append(
                    {
                        "cart_item_id": str(item.id),
                        "product_id": str(item.product_id),
                        "variant_id": str(item.variant_id) if item.variant_id else None,
                        "quantity_in_cart": item.quantity,
                        "available_qty": stock_info["available_qty"],
                        "is_backorder_allowed": stock_info["allow_backorder"],
                    }
                )

        return {
            "cart_id": str(cart_id),
            "items_with_price_changes": items_with_price_changes,
            "items_out_of_stock": items_out_of_stock,
            "total_price_difference": float(total_price_difference),
            "is_valid": len(items_out_of_stock) == 0,  # Cart is valid if no out-of-stock items
        }

    async def _get_storefront_product_assignment(
        self, storefront_id: uuid.UUID, product_id: uuid.UUID
    ) -> Optional[StorefrontProduct]:
        """Get storefront-product assignment if exists."""
        query = select(StorefrontProduct).where(
            and_(
                StorefrontProduct.storefront_id == storefront_id,
                StorefrontProduct.product_id == product_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_current_product_price(
        self,
        product_id: uuid.UUID,
        variant_id: Optional[uuid.UUID],
        storefront_id: uuid.UUID,
    ) -> Decimal:
        """Get current price for a product/variant in a specific storefront."""
        # Get base product price
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundException("Product", product_id)

        base_price = product.base_price

        # Apply variant price adjustment if variant exists
        if variant_id:
            variant = await self.product_variant_repo.get_by_id(variant_id)
            if variant:
                base_price += variant.price_adjustment

        # Check for storefront-specific custom price
        storefront_product = await self._get_storefront_product_assignment(
            storefront_id, product_id
        )
        if storefront_product and storefront_product.custom_price is not None:
            price = storefront_product.custom_price
            # Still apply variant adjustment on top of custom price
            if variant_id and variant:
                price += variant.price_adjustment
            return price

        return base_price

    async def _get_product_stock_info(
        self, product_id: uuid.UUID, variant_id: Optional[uuid.UUID]
    ) -> Dict[str, Any]:
        """Get stock information for a product or variant."""
        query = select(Inventory).where(
            and_(
                Inventory.product_id == product_id,
                Inventory.variant_id == variant_id if variant_id else Inventory.variant_id.is_(None),
            )
        )
        result = await self.session.execute(query)
        inventory = result.scalar_one_or_none()

        if inventory:
            return {
                "available_qty": inventory.available_qty,
                "track_inventory": inventory.track_inventory,
                "allow_backorder": inventory.allow_backorder,
            }
        else:
            # No inventory record - assume unlimited stock
            return {
                "available_qty": 999999,
                "track_inventory": False,
                "allow_backorder": True,
            }