#!/usr/bin/env python3
"""Initialize database tables for production."""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.db.base import Base

# Import ALL models to register them with Base.metadata
from src.models.user import User
from src.models.document import ProcurementDocument
from src.models.company import CompanyProfile  # Note: company.py not company_profile.py
from src.models.bid import BidResponse
from src.models.audit import AuditLog
from src.models.compliance import ComplianceCheck
from src.models.events import ProcessingEvent
from src.models.requirements import ExtractedRequirements
from src.models.match import CapabilityMatch

from src.core.config import get_settings


def init_database():
    """Initialize database with all tables."""
    settings = get_settings()

    # Convert async URL to sync
    db_url = str(settings.database_url)
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")

    print(f"Connecting to database...")
    engine = create_engine(db_url)

    # Test connection
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print(f"✅ Database connected: {result.scalar()}")

    # Create all tables
    print("Creating tables...")
    Base.metadata.create_all(engine)

    # List created tables
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        print(f"✅ Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")

    print("✅ Database initialization complete!")
    return True


if __name__ == "__main__":
    init_database()