"""Add repair_cost to unit_inventory_items.

Damage used to be priced one way: quantity times the replacement cost,
for anything recorded as damaged or missing. That charged an item worn to
"fair" the price of a new one, when in practice it is repaired and only
the repair is owed. Fair now prices against this column; damaged and
missing keep pricing against replacement_cost.

Safe to run more than once:

    python scripts/maintenance/add_inventory_repair_cost.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402

STATEMENTS = [
    "ALTER TABLE unit_inventory_items ADD COLUMN IF NOT EXISTS repair_cost NUMERIC(12,2) NOT NULL DEFAULT 0",
]


def main():
    app = create_app()
    with app.app_context():
        exists = db.session.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'unit_inventory_items'"
        )).first()
        if not exists:
            print("unit_inventory_items does not exist yet — run "
                  "create_unit_inventory_table.py first.")
            return 1

        for stmt in STATEMENTS:
            db.session.execute(text(stmt))
            print("  ok:", stmt.split("IF NOT EXISTS")[-1].strip()[:60])
        db.session.commit()

        cols = db.session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'unit_inventory_items' ORDER BY ordinal_position"
        )).scalars().all()
        print("\nunit_inventory_items now has", len(cols), "columns:")
        print("  " + ", ".join(cols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
