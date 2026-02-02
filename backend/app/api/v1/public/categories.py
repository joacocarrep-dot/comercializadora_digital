"""
Public category endpoints for storefronts.

Provides access to category hierarchy for storefronts.
Uses API key authentication via StorefrontMiddleware.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_storefront, get_db, get_category_service
from app.core.exceptions import NotFoundException
from app.models.storefront import Storefront
from app.models.category import Category
from app.models.product import Product
from app.models.storefront_product import StorefrontProduct
from app.schemas.public.category import CategoryTreeResponse, CategoryTreeNode, CategoryDetailResponse, CategoryFlatResponse
from app.services import CategoryService

router = APIRouter()


@router.get(
    "",
    response_model=CategoryTreeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get hierarchical tree of categories for current storefront",
)
async def get_category_tree(
    storefront: Storefront = Depends(get_current_storefront),
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = Query(False, description="Whether to include inactive categories"),
):
    """
    Get complete hierarchical tree of categories for the current storefront.
    
    Structures categories as nested tree (parents with children).
    Includes product count per category based on active products assigned to the storefront.
    Orders by position at each level.
    
    Requires X-API-Key header for storefront identification.
    """
    # Get category service
    category_service = CategoryService(db)
    
    # Get category tree from service
    tree_data = await category_service.get_tree(
        storefront_id=storefront.id,
        include_inactive=include_inactive
    )
    
    # Calculate product counts for each category
    # We'll enhance the tree data with product counts
    enhanced_tree = await _enhance_tree_with_product_counts(tree_data, storefront.id, db)
    
    return CategoryTreeResponse(data=enhanced_tree)


@router.get(
    "/{slug}",
    response_model=CategoryDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get category details by slug",
)
async def get_category_by_slug(
    slug: str,
    storefront: Storefront = Depends(get_current_storefront),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed category information by slug.
    
    Returns category details including parent, immediate children,
    and product count for the current storefront.
    
    Requires X-API-Key header for storefront identification.
    """
    # Find category by slug
    category_query = select(Category).where(Category.slug == slug)
    category_result = await db.execute(category_query)
    category = category_result.scalar_one_or_none()
    
    if not category or not category.is_active:
        raise NotFoundException("Category", slug)
    
    # Get parent category if exists
    parent = None
    if category.parent_id:
        parent_query = select(Category).where(Category.id == category.parent_id)
        parent_result = await db.execute(parent_query)
        parent_cat = parent_result.scalar_one_or_none()
        if parent_cat:
            parent = CategoryFlatResponse(
                id=parent_cat.id,
                name=parent_cat.name,
                slug=parent_cat.slug,
                description=parent_cat.description,
                image_url=parent_cat.image_url,
                position=parent_cat.position,
                parent_id=parent_cat.parent_id,
                product_count=0  # We'd need to calculate this separately
            )
    
    # Get immediate children
    children_query = (
        select(Category)
        .where(
            and_(
                Category.parent_id == category.id,
                Category.is_active == True,
            )
        )
        .order_by(Category.position)
    )
    children_result = await db.execute(children_query)
    children = list(children_result.scalars().all())
    
    # Transform children to flat response
    child_responses = []
    for child in children:
        # Calculate product count for this child in the current storefront
        product_count = await _count_products_in_category(child.id, storefront.id, db)
        
        child_response = CategoryFlatResponse(
            id=child.id,
            name=child.name,
            slug=child.slug,
            description=child.description,
            image_url=child.image_url,
            position=child.position,
            parent_id=child.parent_id,
            product_count=product_count,
        )
        child_responses.append(child_response)
    
    # Calculate product count for this category in the current storefront
    product_count = await _count_products_in_category(category.id, storefront.id, db)
    
    return CategoryDetailResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        image_url=category.image_url,
        position=category.position,
        parent_id=category.parent_id,
        parent=parent,
        children=child_responses,
        product_count=product_count,
        is_active=category.is_active,
    )


async def _enhance_tree_with_product_counts(
    tree_data: list, 
    storefront_id: int, 
    db: AsyncSession
) -> list:
    """
    Enhance category tree with product counts for the given storefront.
    
    Args:
        tree_data: Raw tree data from CategoryService.get_tree()
        storefront_id: ID of storefront to filter products
        db: Database session
        
    Returns:
        Enhanced tree with product counts
    """
    if not tree_data:
        return []
    
    enhanced_tree = []
    
    for category_node in tree_data:
        # Calculate product count for this category in the storefront
        product_count = await _count_products_in_category(
            category_node["id"], 
            storefront_id, 
            db
        )
        
        # Recursively enhance children
        enhanced_children = await _enhance_tree_with_product_counts(
            category_node.get("children", []),
            storefront_id,
            db
        )
        
        # Create enhanced node
        enhanced_node = CategoryTreeNode(
            id=category_node["id"],
            name=category_node["name"],
            slug=category_node["slug"],
            description=category_node.get("description"),
            image_url=category_node.get("image_url"),
            position=category_node.get("position", 0),
            children=enhanced_children,
            product_count=product_count,
        )
        
        enhanced_tree.append(enhanced_node)
    
    return enhanced_tree


async def _count_products_in_category(
    category_id: int, 
    storefront_id: int, 
    db: AsyncSession
) -> int:
    """
    Count active products in a category for a specific storefront.
    
    Args:
        category_id: Category ID
        storefront_id: Storefront ID
        db: Database session
        
    Returns:
        Number of active products in the category for the storefront
    """
    # Count products in this category that are:
    # 1. Active
    # 2. Assigned to the storefront and active in storefront
    # 3. Not considering subcategories (only direct category assignment)
    
    query = (
        select(Product.id)
        .join(StorefrontProduct, Product.id == StorefrontProduct.product_id)
        .where(
            and_(
                Product.category_id == category_id,
                Product.is_active == True,
                StorefrontProduct.storefront_id == storefront_id,
                StorefrontProduct.is_active == True,
            )
        )
        .distinct()
    )
    
    result = await db.execute(query)
    product_ids = list(result.scalars().all())
    
    return len(product_ids)