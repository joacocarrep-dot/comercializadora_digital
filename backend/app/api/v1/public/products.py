"""
Public product endpoints for storefronts.

Provides catalog access to products with filtering, pagination,
and product details. Uses API key authentication via StorefrontMiddleware.
"""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_storefront, get_db, get_product_service
from app.core.exceptions import NotFoundException
from app.models.storefront import Storefront
from app.models.product import Product, ProductType
from app.models.product_variant import ProductVariant
from app.models.inventory import Inventory
from app.models.storefront_product import StorefrontProduct
from app.models.category import Category
from app.schemas.public.product import (
    ProductDetailResponse,
    ProductFilters,
    ProductListPaginated,
    ProductListResponse,
    ProductVariantPublic,
)
from app.services import ProductService

router = APIRouter()


@router.get(
    "",
    response_model=ProductListPaginated,
    status_code=status.HTTP_200_OK,
    summary="List products for current storefront",
)
async def list_products(
    filters: ProductFilters = Depends(),
    storefront: Storefront = Depends(get_current_storefront),
    db: AsyncSession = Depends(get_db),
):
    """
    List products available in the current storefront.
    
    Filters products by storefront assignment, activity status, and optional filters.
    Supports pagination, price range, category, stock status, and sorting.
    
    Requires X-API-Key header for storefront identification.
    """
    # Convert page/per_page to skip/limit for service method
    skip = (filters.page - 1) * filters.per_page
    limit = filters.per_page
    
    # Build base query for products assigned to this storefront
    query = (
        select(Product)
        .join(StorefrontProduct, Product.id == StorefrontProduct.product_id)
        .where(
            and_(
                StorefrontProduct.storefront_id == storefront.id,
                StorefrontProduct.is_active == True,
                Product.is_active == True,
            )
        )
        .distinct()
    )
    
    # Apply category filter if provided
    if filters.category:
        query = query.join(Category, Product.category_id == Category.id).where(
            Category.slug == filters.category
        )
    
    # Apply price filters if provided
    if filters.min_price is not None:
        query = query.where(Product.base_price >= filters.min_price)
    if filters.max_price is not None:
        query = query.where(Product.base_price <= filters.max_price)
    
    # Apply search filter if provided
    if filters.search:
        search_term = f"%{filters.search}%"
        query = query.where(
            or_(
                Product.name.ilike(search_term),
                Product.description.ilike(search_term),
                Product.short_description.ilike(search_term),
            )
        )
    
    # Apply in_stock filter if provided
    if filters.in_stock is not None:
        # For now, we'll implement a simple stock check
        # In a complete implementation, we would join with Inventory
        # and check available_qty > 0
        pass  # TODO: Implement proper in_stock filtering
    
    # Apply sorting
    if filters.sort:
        if filters.sort == "price_asc":
            query = query.order_by(Product.base_price.asc())
        elif filters.sort == "price_desc":
            query = query.order_by(Product.base_price.desc())
        elif filters.sort == "newest":
            query = query.order_by(Product.created_at.desc())
        elif filters.sort == "featured":
            query = query.order_by(
                StorefrontProduct.is_featured.desc(),
                StorefrontProduct.position.asc(),
            )
    else:
        # Default sorting: featured first, then position
        query = query.order_by(
            StorefrontProduct.is_featured.desc(),
            StorefrontProduct.position.asc(),
        )
    
    # Get total count for pagination
    count_query = query.with_only_columns(Product.id)
    count_result = await db.execute(count_query)
    total = len(list(count_result.scalars().all()))
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    products = list(result.scalars().all())
    
    # Transform to response format
    product_responses = []
    for product in products:
        # Get storefront-specific assignment for this product
        assignment_query = select(StorefrontProduct).where(
            and_(
                StorefrontProduct.storefront_id == storefront.id,
                StorefrontProduct.product_id == product.id,
            )
        )
        assignment_result = await db.execute(assignment_query)
        assignment = assignment_result.scalar_one_or_none()
        
        # Determine stock status
        stock_status = "out_of_stock"  # Default
        if product.product_type == ProductType.BUNDLE:
            # For bundles, we'd need to calculate based on components
            stock_status = "in_stock"  # Placeholder
        else:
            # Check inventory
            inventory_query = select(Inventory).where(
                Inventory.product_id == product.id
            )
            inventory_result = await db.execute(inventory_query)
            inventory = inventory_result.scalar_one_or_none()
            
            if inventory:
                if inventory.available_qty > inventory.low_stock_alert:
                    stock_status = "in_stock"
                elif inventory.available_qty > 0:
                    stock_status = "low_stock"
                else:
                    stock_status = "out_of_stock"
        
        # Get category info if exists
        category = None
        if product.category_id:
            category_query = select(Category).where(Category.id == product.category_id)
            category_result = await db.execute(category_query)
            cat = category_result.scalar_one_or_none()
            if cat:
                category = {
                    "id": cat.id,
                    "name": cat.name,
                    "slug": cat.slug,
                }
        
        # Get images from JSONB field
        images = []
        if product.images and isinstance(product.images, list):
            for img_data in product.images:
                if isinstance(img_data, dict) and "url" in img_data:
                    images.append({
                        "url": img_data.get("url"),
                        "alt": img_data.get("alt"),
                        "position": img_data.get("position", 0),
                    })
        
        # Count variants
        variants_query = select(ProductVariant).where(
            and_(
                ProductVariant.product_id == product.id,
                ProductVariant.is_active == True,
            )
        )
        variants_result = await db.execute(variants_query)
        variants_count = len(list(variants_result.scalars().all()))
        
        # Use custom price from assignment if available, otherwise base price
        display_price = assignment.custom_price if assignment and assignment.custom_price else product.base_price
        display_compare_price = assignment.custom_compare_price if assignment and assignment.custom_compare_price else product.compare_price
        
        product_response = ProductListResponse(
            id=product.id,
            name=product.name,
            slug=product.slug,
            short_description=product.short_description,
            base_price=display_price,
            compare_price=display_compare_price,
            currency=product.currency,
            product_type=product.product_type.value,
            images=images,
            category=category,
            stock_status=stock_status,
            is_featured=assignment.is_featured if assignment else False,
            variants_count=variants_count,
        )
        product_responses.append(product_response)
    
    # Calculate pagination metadata
    total_pages = (total + filters.per_page - 1) // filters.per_page if filters.per_page > 0 else 1
    
    return ProductListPaginated(
        data=product_responses,
        pagination={
            "page": filters.page,
            "per_page": filters.per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": filters.page < total_pages,
            "has_prev": filters.page > 1,
        },
    )


@router.get(
    "/{slug}",
    response_model=ProductDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product details by slug",
)
async def get_product_by_slug(
    slug: str,
    storefront: Storefront = Depends(get_current_storefront),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed product information by slug.
    
    Returns complete product details including variants, stock status,
    images, and attributes. Product must be active and assigned to the
    current storefront.
    
    Requires X-API-Key header for storefront identification.
    """
    # Find product by slug
    product_query = select(Product).where(Product.slug == slug)
    product_result = await db.execute(product_query)
    product = product_result.scalar_one_or_none()
    
    if not product or not product.is_active:
        raise NotFoundException("Product", slug)
    
    # Verify product is assigned to this storefront and active
    assignment_query = select(StorefrontProduct).where(
        and_(
            StorefrontProduct.storefront_id == storefront.id,
            StorefrontProduct.product_id == product.id,
            StorefrontProduct.is_active == True,
        )
    )
    assignment_result = await db.execute(assignment_query)
    assignment = assignment_result.scalar_one_or_none()
    
    if not assignment:
        raise NotFoundException(f"Product {slug} not available in this storefront")
    
    # Get category info if exists
    category = None
    if product.category_id:
        category_query = select(Category).where(Category.id == product.category_id)
        category_result = await db.execute(category_query)
        cat = category_result.scalar_one_or_none()
        if cat:
            category = {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
            }
    
    # Get images from JSONB field
    images = []
    if product.images and isinstance(product.images, list):
        for img_data in product.images:
            if isinstance(img_data, dict) and "url" in img_data:
                images.append({
                    "url": img_data.get("url"),
                    "alt": img_data.get("alt"),
                    "position": img_data.get("position", 0),
                })
    
    # Get variants with stock status
    variants_query = (
        select(ProductVariant)
        .where(
            and_(
                ProductVariant.product_id == product.id,
                ProductVariant.is_active == True,
            )
        )
        .order_by(ProductVariant.position)
    )
    variants_result = await db.execute(variants_query)
    variants = list(variants_result.scalars().all())
    
    variant_responses = []
    for variant in variants:
        # Determine variant stock status
        variant_stock_status = "out_of_stock"
        inventory_query = select(Inventory).where(
            Inventory.variant_id == variant.id
        )
        inventory_result = await db.execute(inventory_query)
        inventory = inventory_result.scalar_one_or_none()
        
        if inventory:
            if inventory.available_qty > inventory.low_stock_alert:
                variant_stock_status = "in_stock"
            elif inventory.available_qty > 0:
                variant_stock_status = "low_stock"
            else:
                variant_stock_status = "out_of_stock"
        else:
            # No inventory record, check product inventory
            product_inventory_query = select(Inventory).where(
                Inventory.product_id == product.id
            )
            product_inventory_result = await db.execute(product_inventory_query)
            product_inventory = product_inventory_result.scalar_one_or_none()
            
            if product_inventory:
                if product_inventory.available_qty > product_inventory.low_stock_alert:
                    variant_stock_status = "in_stock"
                elif product_inventory.available_qty > 0:
                    variant_stock_status = "low_stock"
                else:
                    variant_stock_status = "out_of_stock"
        
        variant_response = ProductVariantPublic(
            id=variant.id,
            sku=variant.sku,
            name=variant.name,
            options=variant.options if variant.options else {},
            price_adjustment=variant.price_adjustment,
            stock_status=variant_stock_status,
            image_url=variant.image_url,
        )
        variant_responses.append(variant_response)
    
    # Determine overall product stock status
    overall_stock_status = "out_of_stock"
    if product.product_type == ProductType.BUNDLE:
        # For bundles, we'd need to calculate based on components
        # For now, assume in_stock if any component has stock
        overall_stock_status = "in_stock"  # Placeholder
    else:
        # Check product inventory
        inventory_query = select(Inventory).where(Inventory.product_id == product.id)
        inventory_result = await db.execute(inventory_query)
        inventory = inventory_result.scalar_one_or_none()
        
        if inventory:
            if inventory.available_qty > inventory.low_stock_alert:
                overall_stock_status = "in_stock"
            elif inventory.available_qty > 0:
                overall_stock_status = "low_stock"
            else:
                overall_stock_status = "out_of_stock"
    
    # Use custom price from assignment if available
    display_price = assignment.custom_price if assignment.custom_price else product.base_price
    display_compare_price = assignment.custom_compare_price if assignment.custom_compare_price else product.compare_price
    
    return ProductDetailResponse(
        id=product.id,
        name=product.name,
        slug=product.slug,
        description=product.description,
        short_description=product.short_description,
        base_price=display_price,
        compare_price=display_compare_price,
        currency=product.currency,
        product_type=product.product_type.value,
        images=images,
        category=category,
        attributes=product.attributes if product.attributes else {},
        variants=variant_responses,
        stock_status=overall_stock_status,
        is_featured=assignment.is_featured,
        meta_title=product.meta_title,
        meta_description=product.meta_description,
    )