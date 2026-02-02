"""
Inventory service for business logic related to stock management.

Handles stock updates, availability checks, and inventory validations.
"""
import uuid
from typing import Optional, Tuple

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.repositories.base import BaseRepository


class InventoryService:
    """
    Service for inventory business logic operations.
    
    Attributes:
        session: Async database session
        inventory_repo: BaseRepository for Inventory model
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize inventory service with database session.
        
        Args:
            session: Async database session
        """
        self.session = session
        self.inventory_repo = BaseRepository(Inventory, session)
    
    async def update_stock(
        self,
        product_id: Optional[uuid.UUID] = None,
        variant_id: Optional[uuid.UUID] = None,
        quantity_change: int = 0,
        allow_negative: bool = False,
        override: bool = False
    ) -> Inventory:
        """
        Update stock quantity for a product or variant.
        
        Args:
            product_id: Product ID (optional if variant_id provided)
            variant_id: Variant ID (optional if product_id provided)
            quantity_change: Amount to add (positive) or subtract (negative)
            allow_negative: Whether to allow negative stock after update
            override: Whether to set quantity directly instead of adding
            
        Returns:
            Updated Inventory record
            
        Raises:
            BadRequestException: If neither product_id nor variant_id provided,
                or if update would result in negative stock and allow_negative=False
            NotFoundException: If inventory record not found
        """
        # Validate at least one identifier is provided
        if not product_id and not variant_id:
            raise BadRequestException(
                "Either product_id or variant_id must be provided"
            )
        
        # Find existing inventory record
        inventory = await self._find_or_create_inventory(product_id, variant_id)
        
        if not inventory.track_inventory:
            raise BadRequestException(
                "Inventory tracking is disabled for this item"
            )
        
        # Calculate new quantity
        if override:
            new_quantity = quantity_change
        else:
            new_quantity = inventory.quantity + quantity_change
        
        # Validate new quantity
        if new_quantity < 0 and not allow_negative:
            raise BadRequestException(
                f"Insufficient stock. Current: {inventory.quantity}, "
                f"Requested change: {quantity_change}"
            )
        
        # Validate reserved_qty doesn't exceed new quantity
        if inventory.reserved_qty > new_quantity:
            if override:
                # If overriding, adjust reserved_qty down
                inventory.reserved_qty = new_quantity
            else:
                raise BadRequestException(
                    f"Cannot reduce quantity below reserved quantity. "
                    f"Reserved: {inventory.reserved_qty}, "
                    f"New quantity would be: {new_quantity}"
                )
        
        # Update inventory
        inventory.quantity = new_quantity
        await self.session.commit()
        await self.session.refresh(inventory)
        
        return inventory
    
    async def get_available_stock(
        self,
        product_id: Optional[uuid.UUID] = None,
        variant_id: Optional[uuid.UUID] = None
    ) -> int:
        """
        Get available stock quantity (quantity - reserved_qty).
        
        Args:
            product_id: Product ID (optional if variant_id provided)
            variant_id: Variant ID (optional if product_id provided)
            
        Returns:
            Available stock quantity
            
        Raises:
            BadRequestException: If neither product_id nor variant_id provided
            NotFoundException: If inventory record not found
        """
        # Validate at least one identifier is provided
        if not product_id and not variant_id:
            raise BadRequestException(
                "Either product_id or variant_id must be provided"
            )
        
        # Find inventory record
        inventory = await self._find_inventory(product_id, variant_id)
        
        if not inventory:
            # Return 0 if no inventory record exists
            return 0
        
        if not inventory.track_inventory:
            # Return a large number if inventory tracking is disabled
            return 999999
        
        return inventory.available_qty
    
    async def check_stock(
        self,
        product_id: Optional[uuid.UUID] = None,
        variant_id: Optional[uuid.UUID] = None,
        requested_quantity: int = 1,
        raise_exception: bool = True
    ) -> bool:
        """
        Check if sufficient stock is available.
        
        Args:
            product_id: Product ID (optional if variant_id provided)
            variant_id: Variant ID (optional if product_id provided)
            requested_quantity: Quantity to check availability for
            raise_exception: Whether to raise exception if insufficient stock
            
        Returns:
            True if sufficient stock is available, False otherwise
            
        Raises:
            BadRequestException: If neither product_id nor variant_id provided,
                or if insufficient stock and raise_exception=True
        """
        # Validate at least one identifier is provided
        if not product_id and not variant_id:
            raise BadRequestException(
                "Either product_id or variant_id must be provided"
            )
        
        # Validate requested quantity
        if requested_quantity < 0:
            raise BadRequestException(
                f"Requested quantity must be non-negative: {requested_quantity}"
            )
        
        # Find inventory record
        inventory = await self._find_inventory(product_id, variant_id)
        
        # Handle cases where no inventory record exists
        if not inventory:
            if raise_exception:
                raise BadRequestException(
                    f"No inventory record found for product_id={product_id}, variant_id={variant_id}"
                )
            return False
        
        # Check if inventory tracking is disabled
        if not inventory.track_inventory:
            return True
        
        # Check if backorders are allowed
        if inventory.allow_backorder:
            return True
        
        # Check available stock
        available = inventory.available_qty
        has_stock = available >= requested_quantity
        
        if not has_stock and raise_exception:
            raise BadRequestException(
                f"Insufficient stock. Available: {available}, Requested: {requested_quantity}"
            )
        
        return has_stock
    
    async def _find_inventory(
        self,
        product_id: Optional[uuid.UUID] = None,
        variant_id: Optional[uuid.UUID] = None
    ) -> Optional[Inventory]:
        """
        Find inventory record by product_id and/or variant_id.
        
        Args:
            product_id: Product ID
            variant_id: Variant ID
            
        Returns:
            Inventory record or None if not found
        """
        query = select(Inventory)
        
        if product_id and variant_id:
            query = query.where(
                and_(
                    Inventory.product_id == product_id,
                    Inventory.variant_id == variant_id
                )
            )
        elif product_id:
            query = query.where(
                and_(
                    Inventory.product_id == product_id,
                    Inventory.variant_id == None
                )
            )
        elif variant_id:
            query = query.where(
                and_(
                    Inventory.product_id == None,
                    Inventory.variant_id == variant_id
                )
            )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def _find_or_create_inventory(
        self,
        product_id: Optional[uuid.UUID] = None,
        variant_id: Optional[uuid.UUID] = None
    ) -> Inventory:
        """
        Find inventory record or create if it doesn't exist.
        
        Args:
            product_id: Product ID
            variant_id: Variant ID
            
        Returns:
            Inventory record
            
        Raises:
            BadRequestException: If product/variant doesn't exist
        """
        # Check if product/variant exists
        if product_id:
            product = await self.session.get(Product, product_id)
            if not product:
                raise BadRequestException(f"Product not found: {product_id}")
        
        if variant_id:
            variant = await self.session.get(ProductVariant, variant_id)
            if not variant:
                raise BadRequestException(f"Product variant not found: {variant_id}")
        
        # Try to find existing inventory record
        inventory = await self._find_inventory(product_id, variant_id)
        
        if inventory:
            return inventory
        
        # Create new inventory record
        inventory_data = {
            "product_id": product_id,
            "variant_id": variant_id,
            "quantity": 0,
            "reserved_qty": 0,
            "low_stock_alert": 5,
            "track_inventory": True,
            "allow_backorder": False,
        }
        
        # For bundle products, disable inventory tracking
        if product_id:
            product = await self.session.get(Product, product_id)
            if product and product.product_type == "bundle":
                inventory_data["track_inventory"] = False
        
        inventory = await self.inventory_repo.create(**inventory_data)
        return inventory