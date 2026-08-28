#!/usr/bin/env python3
"""
Adds units.pax_range — occupant-count bracket ("1-2", "3-4", "5-6") for
residential units, used to compute the fixed monthly water bill shown on
the tenant dashboard. Not used for commercial units (they pay their own
water bill directly).

Safe to run multiple times (IF NOT EXISTS guard).
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Adding units.pax_range...")
    try:
        db.session.execute(db.text("""
            ALTER TABLE units
            ADD COLUMN IF NOT EXISTS pax_range VARCHAR(10) NULL
        """))
        db.session.commit()
        print("   Done.")
    except Exception as e:
        db.session.rollback()
        print(f"   Error: {e}")
        raise

    print("\nMigration complete.")
