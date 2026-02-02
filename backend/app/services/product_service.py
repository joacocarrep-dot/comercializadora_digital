"""
Product service for business logic related to products.

Handles product creation, updates, deletion, storefront assignment,
and bundle stock calculations.
"""
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.models.product import Product, ProductType
from app.models.product_variant import ProductVariant
from app.models.inventory import Inventory
from app.models.bundle_item import BundleItem
from app.models.storefront_product import StorefrontProduct
from app.models.storefront import Storefront
from app.models.supplier import Supplier
from app.models.category import Category
from app.repositories.base import BaseRepository


class ProductService:
    """
    Service for product business logic operations.
    
    Attributes:
        session: Async database session
        product_repo: BaseRepository for Product model
        product_variant_repo: BaseRepository for ProductVariant model
        inventory_repo: BaseRepository for Inventory model
        bundle_item_repo: BaseRepository for BundleItem model
        storefront_product_repo: BaseRepository for StorefrontProduct model
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize product service with database session.
        
        Args:
            session: Async database session
        """
        self.session = session
        self.product_repo = BaseRepository(Product, session)
        self.product_variant_repo = BaseRepository(ProductVariant, session)
        self.inventory_repo = BaseRepository(Inventory, session)
        self.bundle_item_repo = BaseRepository(BundleItem, session)
        self.storefront_product_repo = BaseRepository(StorefrontProduct, session)
    
    async def create_product(self, product_data: Dict[str, Any]) -> Product:
        """
        Create a new product with validation.
        
        Validates slug uniqueness and relationships with Supplier and Category.
        
        Args:
            product_data: Dictionary containing product fields
            
        Returns:
            Created Product instance
            
        Raises:
            BadRequestException: If required fields are missing
            ConflictException: If slug already exists
            NotFoundException: If supplier or category not found
        """
        # Validate required fields
        required_fields = ["name", "slug", "sku", "base_price", "supplier_id"]
        missing_fields = [field for field in required_fields if field not in product_data]
        if missing_fields:
            raise BadRequestException(
                f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate slug uniqueness
        slug_exists = await self._check_slug_exists(product_data["slug"])
        if slug_exists:
            raise ConflictException(f"Product with slug '{product_data['slug']}' already exists")
        
        # Validate supplier exists
        supplier = await self.session.get(Supplier, product_data["supplier_id"])
        if not supplier:
            raise NotFoundException("Supplier", product_data["supplier_id"])
        
        # Validate category exists if provided
        category_id = product_data.get("category_id")
        if category_id:
            category = await self.session.get(Category, category_id)
            if not category:
                raise NotFoundException("Category", category_id)
        
        # Set defaults
        if "product_type" not in product_data:
            product_data["product_type"] = ProductType.PHYSICAL
        
        if "currency" not in product_data:
            product_data["currency"] = "ARS"
        
        if "tax_rate" not in product_data:
            product_data["tax_rate"] = 0
        
        if "is_active" not in product_data:
            product_data["is_active"] = True
        
        if "is_featured" not in product_data:
            product_data["is_featured"] = False
        
        # Create product
        product = await self.product_repo.create(**product_data)
        
        # Create initial inventory record for simple products
        if product.product_type != ProductType.BUNDLE:
            inventory_data = {
                "product_id": product.id,
                "quantity": 0,
                "reserved_qty": 0,
            }
            await self.inventory_repo.create(**inventory_data)
        
        return product
    
    async def update_product(self, product_id: uuid.UUID, update_data: Dict[str, Any]) -> Product:
        """
        Update an existing product.
        
        Validates slug uniqueness (excluding the current product) and updates fields.
        
        Args:
            product_id: ID of product to update
            update_data: Dictionary of fields to update
            
        Returns:
            Updated Product instance
            
        Raises:
            NotFoundException: If product not found
            ConflictException: If new slug already exists (different product)
            BadRequestException: If update data is invalid
        """
        # Get existing product
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundException("Product", product_id)
        
        # Validate slug uniqueness if slug is being updated
        new_slug = update_data.get("slug")
        if new_slug and new_slug != product.slug:
            slug_exists = await self._check_slug_exists(new_slug, exclude_product_id=product_id)
            if slug_exists:
                raise ConflictException(f"Product with slug '{new_slug}' already exists")
        
        # Validate supplier exists if updating supplier_id
        if "supplier_id" in update_data:
            supplier = await self.session.get(Supplier, update_data["supplier_id"])
            if not supplier:
                raise NotFoundException("Supplier", update_data["supplier_id"])
        
        # Validate category exists if updating category_id
        if "category_id" in update_data:
            category_id = update_data["category_id"]
            if category_id:
                category = await self.session.get(Category, category_id)
                if not category:
                    raise NotFoundException("Category", category_id)
        
        # Update product
        updated_product = await self.product_repo.update(product_id, **update_data)
        if not updated_product:
            raise NotFoundException("Product", product_id)
        
        return updated_product
    
    async def delete_product(self, product_id: uuid.UUID) -> bool:
        """
        Delete a product (soft delete if applicable).
        
        Validates that product has no active dependencies (variants, inventory, etc.)
        For soft delete, marks is_active=False.
        
        Args:
            product_id: ID of product to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundException: If product not found
            BadRequestException: If product has active dependencies
        """
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundException("Product", product_id)
        
        # Check for active dependencies
        # Check variants
        variants = await self.product_variant_repo.get_all(filters={"product_id": product_id})
        if variants:
            raise BadRequestException(
                f"Cannot delete product with {len(variants)} active variants. "
                "Delete variants first."
            )
        
        # Check storefront assignments
        storefront_products = await self.storefront_product_repo.get_all(
            filters={"product_id": product_id, "is_active": True}
        )
        if storefront_products:
            raise BadRequestException(
                f"Cannot delete product with {len(storefront_products)} active storefront assignments. "
                "Unassign from storefronts first."
            )
        
        # Check if product is used as component in bundles
        bundle_items = await self.bundle_item_repo.get_all(filters={"product_id": product_id})
        if bundle_items:
            bundle_ids = [str(item.bundle_id) for item in bundle_items]
            raise BadRequestException(
                f"Cannot delete product used in {len(bundle_items)} bundles. "
                f"Bundle IDs: {', '.join(bundle_ids[:5])}"
                f"{'...' if len(bundle_ids) > 5 else ''}"
            )
        
        # Soft delete: mark as inactive
        await self.product_repo.update(product_id, is_active=False)
        return True
    
    async def get_by_storefront(
        self,
        storefront_id: uuid.UUID,
        skip: int = 0,
        limit: Optional[int] = None,
        include_inactive: bool = False
    ) -> Tuple[List[Product], int]:
        """
        Get products assigned to a specific storefront.
        
        Filters products by storefront assignment and activity status.
        Supports pagination.
        
        Args:
            storefront_id: ID of storefront
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_inactive: Whether to include inactive products
            
        Returns:
            Tuple of (list of products, total count)
            
        Raises:
            NotFoundException: If storefront not found
        """
        # Verify storefront exists
        storefront = await self.session.get(Storefront, storefront_id)
        if not storefront:
            raise NotFoundException("Storefront", storefront_id)
        
        # Build query
        query = (
            select(Product)
            .join(StorefrontProduct, Product.id == StorefrontProduct.product_id)
            .where(StorefrontProduct.storefront_id == storefront_id)
        )
        
        if not include_inactive:
            query = query.where(
                and_(
                    Product.is_active == True,
                    StorefrontProduct.is_active == True
                )
            )
        
        # Get total count
        count_query = query.with_only_columns(Product.id)
        count_result = await self.session.execute(count_query)
        total_count = len(list(count_result.scalars().all()))
        
        # Apply pagination
        if limit:
            query = query.offset(skip).limit(limit)
        
        # Order by storefront product position
        query = query.order_by(StorefrontProduct.position)
        
        # Execute query
        result = await self.session.execute(query)
        products = list(result.scalars().all())
        
        return products, total_count
    
    async def assign_to_storefront(
        self,
        storefront_id: uuid.UUID,
        product_id: uuid.UUID,
        custom_price: Optional[float] = None,
        custom_compare_price: Optional[float] = None,
        is_active: bool = True,
        is_featured: bool = False,
        position: int = 0,
        storefront_category_id: Optional[uuid.UUID] = None
    ) -> StorefrontProduct:
        """
        Assign a product to a storefront with custom configuration.
        
        Creates or updates a StorefrontProduct record with custom pricing
        and positioning.
        
        Args:
            storefront_id: ID of storefront
            product_id: ID of product
            custom_price: Optional custom price override
            custom_compare_price: Optional custom compare price override
            is_active: Whether product is active in this storefront
            is_featured: Whether product is featured in this storefront
            position: Position for ordering in storefront
            storefront_category_id: Optional category override for storefront
            
        Returns:
            Created/updated StorefrontProduct instance
            
        Raises:
            NotFoundException: If storefront or product not found
            ConflictException: If assignment already exists
            BadRequestException: If storefront_category_id is invalid
        """
        # Verify storefront exists
        storefront = await self.session.get(Storefront, storefront_id)
        if not storefront:
            raise NotFoundException("Storefront", storefront_id)
        
        # Verify product exists
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundException("Product", product_id)
        
        # Verify storefront category exists if provided
        if storefront_category_id:
            category = await self.session.get(Category, storefront_category_id)
            if not category:
                raise NotFoundException("Category", storefront_category_id)
        
        # Check if assignment already exists
        existing_query = select(StorefrontProduct).where(
            and_(
                StorefrontProduct.storefront_id == storefront_id,
                StorefrontProduct.product_id == product_id
            )
        )
        existing_result = await self.session.execute(existing_query)
        existing_assignment = existing_result.scalar_one_or_none()
        
        if existing_assignment:
            # Update existing assignment
            update_data = {
                "custom_price": custom_price,
                "custom_compare_price": custom_compare_price,
                "is_active": is_active,
                "is_featured": is_featured,
                "position": position,
                "storefront_category_id": storefront_category_id
            }
            # Remove None values to avoid overwriting with null
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            updated = await self.storefront_product_repo.update(
                existing_assignment.id,
                **update_data
            )
            if not updated:
                raise NotFoundException("StorefrontProduct", existing_assignment.id)
            return updated
        else:
            # Create new assignment
            assignment_data = {
                "storefront_id": storefront_id,
                "product_id": product_id,
                "custom_price": custom_price,
                "custom_compare_price": custom_compare_price,
                "is_active": is_active,
                "is_featured": is_featured,
                "position": position,
                "storefront_category_id": storefront_category_id
            }
            return await self.storefront_product_repo.create(**assignment_data)
    
    async def calculate_bundle_stock(self, bundle_product_id: uuid.UUID) -> int:
        """
        Calculate available stock for a bundle product.
        
        Iterates over bundle components and returns the minimum available
        stock based on component availability.
        
        Args:
            bundle_product_id: ID of bundle product
            
        Returns:
            Available stock quantity for the bundle
            
        Raises:
            NotFoundException: If bundle product not found
            BadRequestException: If product is not a bundle
        """
        # Verify product exists and is a bundle
        product = await self.product_repo.get_by_id(bundle_product_id)
        if not product:
            raise NotFoundException("Product", bundle_product_id)
        
        if product.product_type != ProductType.BUNDLE:
            raise BadRequestException(f"Product {bundle_product_id} is not a bundle")
        
        # Get bundle components
        bundle_items_query = (
            select(BundleItem)
            .where(BundleItem.bundle_id == bundle_product_id)
            .options(selectinload(BundleItem.product))
        )
        result = await self.session.execute(bundle_items_query)
        bundle_items = list(result.scalars().all())
        
        if not bundle_items:
            return 0  # Bundle with no components has no stock
        
        min_available = float('inf')
        
        for item in bundle_items:
            # Get available stock for component product
            inventory_query = select(Inventory).where(
                Inventory.product_id == item.product_id
            )
            inventory_result = await self.session.execute(inventory_query)
            inventory_record = inventory_result.scalar_one_or_none()
            
            if not inventory_record:
                # Component has no inventory record = 0 stock
                return 0
            
            if not inventory_record.track_inventory:
                # Component doesn't track inventory = unlimited
                continue
            
            available = inventory_record.available_qty
            # Divide by component quantity needed for one bundle
            component_available = available // item.quantity
            min_available = min(min_available, component_available)
        
        # If all components have unlimited stock, return a high number
        if min_available == float('inf'):
            return 999999  # Arbitrary large number
        
        return max(0, int(min_available))
    
    async def _check_slug_exists(
        self,
        slug: str,
        exclude_product_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Check if a product slug already exists.
        
        Args:
            slug: Slug to check
            exclude_product_id: Optional product ID to exclude from check
            
        Returns:
            True if slug exists, False otherwise
        """
        query = select(Product).where(Product.slug == slug)
        
        if exclude_product_id:
            query = query.where(Product.id != exclude_product_id)
        
        result = await self.session.execute(query)
        product = result.scalar_one_or_none()
        
        return product is not None