#!/usr/bin/env python3
"""Script para verificar el estado de la base de datos."""
import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async def check_db():
    DATABASE_URL = "postgresql+asyncpg://postgres:admin123.@localhost:5432/comercializadora"
    
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.connect() as conn:
        # 1. Verificar tablas existentes
        print("=== TABLAS EXISTENTES ===")
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """))
        tables = [row[0] for row in result]
        for table in tables:
            print(f"  - {table}")
        
        # 2. Verificar columnas de la tabla users
        print("\n=== COLUMNAS DE 'users' ===")
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'users'
            ORDER BY ordinal_position;
        """))
        for row in result:
            print(f"  - {row[0]}: {row[1]}, nullable={row[2]}, default={row[3]}")
        
        # 3. Verificar filas en users
        print("\n=== USUARIOS EXISTENTES ===")
        result = await conn.execute(text("SELECT id, email, user_type, email_verified, phone_verified FROM users;"))
        users = [row for row in result]
        if users:
            for user in users:
                print(f"  - {user[0]}: email={user[1]}, user_type={user[2]}, email_verified={user[3]}, phone_verified={user[4]}")
        else:
            print("  (No hay usuarios)")
        
        # 4. Verificar migraciones aplicadas (alembic_version)
        print("\n=== MIGRACIONES APLICADAS (alembic_version) ===")
        result = await conn.execute(text("SELECT version_num FROM alembic_version;"))
        alembic_versions = [row[0] for row in result]
        for ver in alembic_versions:
            print(f"  - {ver}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_db())