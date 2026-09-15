#!/usr/bin/env python3
"""
Adds concern_follow_ups.unit_inventory_item_id — the inventory item a
follow-up is about, matching the column of the same name on `concerns`.

The model declared it but the table never had it, so every page that loaded
a follow-up raised "column does not exist" and the tenant was shown an
Internal Server Error after filing a concern — the concern itself had
already been saved.

Safe to run multiple times (IF NOT EXISTS guard).
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Adding concern_follow_ups.unit_inventory_item_id...")
    try:
        db.session.execute(db.text("""
            ALTER TABLE concern_follow_ups
            ADD COLUMN IF NOT EXISTS unit_inventory_item_id INTEGER NULL
                REFERENCES unit_inventory_items(id)
        """))
        db.session.commit()
        print("   Done.")
    except Exception as e:
        db.session.rollback()
        print(f"   Error: {e}")
        raise

    print("\nMigration complete.")
