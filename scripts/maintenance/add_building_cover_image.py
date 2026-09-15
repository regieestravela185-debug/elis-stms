#!/usr/bin/env python3
"""
Adds buildings.cover_image — the photograph the homepage shows on each
building's card. Without it the card falls back to a photo of one of the
units inside, which shows a room rather than the building.

Safe to run multiple times (IF NOT EXISTS guard).
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Adding buildings.cover_image...")
    try:
        db.session.execute(db.text("""
            ALTER TABLE buildings
            ADD COLUMN IF NOT EXISTS cover_image VARCHAR(500) NULL
        """))
        db.session.commit()
        print("   Done.")
    except Exception as e:
        db.session.rollback()
        print(f"   Error: {e}")
        raise

    print("\nMigration complete.")
