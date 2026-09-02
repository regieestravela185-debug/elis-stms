"""Let a concern point at the fixture it is about.

A fixture recorded as damaged sat in the inventory doing nothing: no
repair was scheduled from it, and the final settlement would keep
charging for it even after it had been fixed, because nothing connected
the repair back to the item.

Safe to run more than once.

    python scripts/maintenance/link_concerns_to_inventory.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402


def main():
    app = create_app()
    with app.app_context():
        db.session.execute(text(
            "ALTER TABLE concerns ADD COLUMN IF NOT EXISTS "
            "unit_inventory_item_id INTEGER NULL REFERENCES unit_inventory_items(id)"
        ))
        db.session.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_concerns_inventory_item "
            "ON concerns(unit_inventory_item_id)"
        ))
        db.session.commit()
        print("concerns.unit_inventory_item_id ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
