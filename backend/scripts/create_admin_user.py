#!/usr/bin/env python
"""
Script para crear usuario admin de testing
Ejecutar: docker-compose exec app python scripts/create_admin_user.py
"""
import asyncio
import sys
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.config.settings import settings

async def create_admin():
    # Crear engine con tu URL de DB
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Verificar si ya existe un admin
        existing = await session.execute(
            "SELECT id FROM users WHERE email = 'admin@test.com'"
        )
        if existing.first():
            print("✅ Usuario admin@test.com ya existe")
            return
        
        # Crear usuario admin
        admin = User(
            id=uuid4(),
            email="admin@test.com",
            hashed_password=hash_password("Admin123!"),
            role=UserRole.ADMIN,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        session.add(admin)
        await session.commit()
        print(f"✅ Usuario admin creado:")
        print(f"   Email: admin@test.com")
        print(f"   Password: Admin123!")
        print(f"   Role: {admin.role.value}")
        print(f"   ID: {admin.id}")

if __name__ == "__main__":
    asyncio.run(create_admin())