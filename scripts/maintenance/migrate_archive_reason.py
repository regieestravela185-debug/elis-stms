#!/usr/bin/env python3
"""
Adds users.archive_reason — a short human-readable note on WHY an account
was archived (e.g. "Moved out", "Contract expired", "Manually archived by
admin"), shown next to the Archived badge on the Customers page and user
detail page so admin doesn't have to guess.

Safe to run multiple times (IF NOT EXISTS guard).
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Adding users.archive_reason...")
    try:
        db.session.execute(db.text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS archive_reason VARCHAR(255) NULL
        """))
        db.session.commit()
        print("   Done.")
    except Exception as e:
        db.session.rollback()
        print(f"   Error: {e}")
        raise

    print("\nMigration complete.")
