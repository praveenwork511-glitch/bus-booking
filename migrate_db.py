#!/usr/bin/env python3
"""
Migration script to add photo_filename column to bus table
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL
database_url = os.getenv('DATABASE_URL')
if not database_url:
    print("ERROR: DATABASE_URL not found in .env")
    exit(1)

# Create engine
engine = create_engine(database_url)

# Execute migration
with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE bus ADD COLUMN IF NOT EXISTS photo_filename VARCHAR(255)"))
        conn.execute(text("ALTER TABLE schedule ADD COLUMN IF NOT EXISTS days_of_week VARCHAR(50)"))
        print("✅ Database migration completed successfully!")
        print("   - Added photo_filename column to bus table")
        print("   - Added days_of_week column to schedule table")
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        exit(1)
