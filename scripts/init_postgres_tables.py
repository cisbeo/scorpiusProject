#!/usr/bin/env python3
"""Initialize PostgreSQL database tables."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Force PostgreSQL
os.environ["DATABASE_URL"] = "postgresql+asyncpg://scorpius:scorpiusdev@localhost:5434/scorpius_dev"

from src.db.session import async_engine
from src.db.base import Base

# Import all models to ensure they are registered
# This will import all models via __init__.py
from src.models import *


async def init_tables():
    """Create all tables in PostgreSQL."""
    print("🚀 Initializing PostgreSQL tables...")
    print(f"📦 Database URL: {os.environ['DATABASE_URL']}")

    async with async_engine.begin() as conn:
        # Drop all tables first (for clean state)
        print("🗑️  Dropping existing tables...")
        await conn.run_sync(Base.metadata.drop_all)

        # Create all tables
        print("📋 Creating tables...")
        await conn.run_sync(Base.metadata.create_all)

        print("✅ All tables created successfully!")

    # List created tables
    async with async_engine.begin() as conn:
        result = await conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        tables = [row[0] for row in result]
        print(f"\n📊 Created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"   - {table}")


if __name__ == "__main__":
    asyncio.run(init_tables())