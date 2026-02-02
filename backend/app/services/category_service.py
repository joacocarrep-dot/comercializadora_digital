"""
Category service for business logic related to categories.

Handles category creation, updates, deletion, and hierarchical tree operations.
"""
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.models.category import Category
from app.repositories.base import BaseRepository


class CategoryService:
    """
    Service for category business logic operations.
    
    Attributes:
        session: Async database session
        category_repo: BaseRepository for Category model
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize category service with database session.
        
        Args:
            session: Async database session
        """
        self.session = session
        self.category_repo = BaseRepository(Category, session)
    
    async def create_category(self, category_data: Dict[str, Any]) -> Category:
        """
        Create a new category with validation.
        
        Validates slug uniqueness and parent relationship.
        Assigns automatic position if not specified.
        
        Args:
            category_data: Dictionary containing category fields
            
        Returns:
            Created Category instance
            
        Raises:
            BadRequestException: If required fields are missing
            ConflictException: If slug already exists
            NotFoundException: If parent category not found
        """
        # Validate required fields
        required_fields = ["name", "slug"]
        missing_fields = [field for field in required_fields if field not in category_data]
        if missing_fields:
            raise BadRequestException(
                f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate slug uniqueness
        slug_exists = await self._check_slug_exists(category_data["slug"])
        if slug_exists:
            raise ConflictException(f"Category with slug '{category_data['slug']}' already exists")
        
        # Validate parent exists if provided
        parent_id = category_data.get("parent_id")
        if parent_id:
            parent = await self.category_repo.get_by_id(parent_id)
            if not parent:
                raise NotFoundException("Category", parent_id)
        
        # Set defaults
        if "position" not in category_data:
            # Determine next position for siblings
            category_data["position"] = await self._get_next_position(parent_id)
        
        if "is_active" not in category_data:
            category_data["is_active"] = True
        
        # Create category
        category = await self.category_repo.create(**category_data)
        return category
    
    async def get_tree(
        self,
        storefront_id: Optional[uuid.UUID] = None,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get complete hierarchical tree of categories.
        
        Structures categories as nested tree (parents with children).
        Orders by position at each level.
        
        Args:
            storefront_id: Optional storefront ID to filter categories
            include_inactive: Whether to include inactive categories
            
        Returns:
            List of root categories with nested children
        """
        # Build base query
        query = select(Category)
        
        if not include_inactive:
            query = query.where(Category.is_active == True)
        
        # Apply storefront filtering if specified
        # Note: Storefront filtering would require additional logic
        # For now, we'll implement the basic tree structure
        # Storefront-specific filtering can be added later
        
        # Order by parent_id NULLS FIRST (root categories first), then position
        query = query.order_by(Category.parent_id, Category.position)
        
        # Execute query
        result = await self.session.execute(query)
        all_categories = list(result.scalars().all())
        
        # Build tree structure
        return self._build_category_tree(all_categories)
    
    async def update_category(
        self,
        category_id: uuid.UUID,
        update_data: Dict[str, Any]
    ) -> Category:
        """
        Update an existing category.
        
        Validates slug uniqueness (excluding the current category) and
        prevents circular references when changing parent_id.
        
        Args:
            category_id: ID of category to update
            update_data: Dictionary of fields to update
            
        Returns:
            Updated Category instance
            
        Raises:
            NotFoundException: If category not found
            ConflictException: If new slug already exists (different category)
            BadRequestException: If parent change creates a cycle
        """
        # Get existing category
        category = await self.category_repo.get_by_id(category_id)
        if not category:
            raise NotFoundException("Category", category_id)
        
        # Validate slug uniqueness if slug is being updated
        new_slug = update_data.get("slug")
        if new_slug and new_slug != category.slug:
            slug_exists = await self._check_slug_exists(new_slug, exclude_category_id=category_id)
            if slug_exists:
                raise ConflictException(f"Category with slug '{new_slug}' already exists")
        
        # Validate parent change doesn't create cycle
        new_parent_id = update_data.get("parent_id")
        if new_parent_id is not None:
            # Check for circular reference
            if new_parent_id == category_id:
                raise BadRequestException("Category cannot be its own parent")
            
            # Check if new parent exists
            new_parent = await self.category_repo.get_by_id(new_parent_id)
            if not new_parent:
                raise NotFoundException("Category", new_parent_id)
            
            # Check if new parent is a descendant of this category
            if await self._is_descendant(new_parent_id, category_id):
                raise BadRequestException(
                    "Cannot set parent to a descendant (would create circular reference)"
                )
        
        # Update category
        updated_category = await self.category_repo.update(category_id, **update_data)
        if not updated_category:
            raise NotFoundException("Category", category_id)
        
        return updated_category
    
    async def _check_slug_exists(
        self,
        slug: str,
        exclude_category_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Check if a category slug already exists.
        
        Args:
            slug: Slug to check
            exclude_category_id: Optional category ID to exclude from check
            
        Returns:
            True if slug exists, False otherwise
        """
        query = select(Category).where(Category.slug == slug)
        
        if exclude_category_id:
            query = query.where(Category.id != exclude_category_id)
        
        result = await self.session.execute(query)
        category = result.scalar_one_or_none()
        
        return category is not None
    
    async def _get_next_position(self, parent_id: Optional[uuid.UUID]) -> int:
        """
        Get next available position for a category under a given parent.
        
        Args:
            parent_id: Optional parent category ID
            
        Returns:
            Next available position
        """
        query = select(Category).where(Category.parent_id == parent_id)
        result = await self.session.execute(query)
        siblings = list(result.scalars().all())
        
        if not siblings:
            return 0
        
        # Find max position
        max_position = max(category.position for category in siblings)
        return max_position + 1
    
    def _build_category_tree(self, categories: List[Category]) -> List[Dict[str, Any]]:
        """
        Build hierarchical tree structure from flat category list.
        
        Args:
            categories: List of Category instances
            
        Returns:
            List of root categories with nested children
        """
        # Create dictionary for quick lookup
        categories_by_id = {category.id: category for category in categories}
        children_by_parent = {}
        
        # Group children by parent
        for category in categories:
            parent_id = category.parent_id
            if parent_id not in children_by_parent:
                children_by_parent[parent_id] = []
            children_by_parent[parent_id].append(category)
        
        # Build tree recursively
        def build_branch(parent_id: Optional[uuid.UUID]) -> List[Dict[str, Any]]:
            children = children_by_parent.get(parent_id, [])
            # Sort children by position
            children = sorted(children, key=lambda c: c.position)
            
            branch = []
            for child in children:
                child_dict = {
                    "id": child.id,
                    "name": child.name,
                    "slug": child.slug,
                    "description": child.description,
                    "image_url": child.image_url,
                    "position": child.position,
                    "is_active": child.is_active,
                    "created_at": child.created_at,
                    "updated_at": child.updated_at,
                    "children": build_branch(child.id)
                }
                branch.append(child_dict)
            
            return branch
        
        # Return root categories (parent_id is None)
        return build_branch(None)
    
    async def _is_descendant(self, potential_descendant_id: uuid.UUID, ancestor_id: uuid.UUID) -> bool:
        """
        Check if a category is a descendant of another category.
        
        Args:
            potential_descendant_id: ID of potential descendant
            ancestor_id: ID of potential ancestor
            
        Returns:
            True if potential_descendant is a descendant of ancestor
        """
        if potential_descendant_id == ancestor_id:
            return False
        
        current_id = potential_descendant_id
        visited = set()
        
        while current_id:
            if current_id == ancestor_id:
                return True
            
            # Prevent infinite loops in case of data corruption
            if current_id in visited:
                break
            visited.add(current_id)
            
            # Get current category
            query = select(Category).where(Category.id == current_id)
            result = await self.session.execute(query)
            current_category = result.scalar_one_or_none()
            
            if not current_category or not current_category.parent_id:
                break
            
            current_id = current_category.parent_id
        
        return False