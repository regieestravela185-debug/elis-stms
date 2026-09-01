"""Columns the final deposit settlement needs.

Residential tenants are month to month and do not always give notice, so
move-out is recorded when the administrator learns of it rather than
derived from a contract end. The deposit is then held for one month while
the final rent, utilities and any damage are totalled.

Damage is priced from the unit's inventory, so each fixture carries what
it costs to replace — a deduction both sides can check, rather than a
figure the administrator has to justify from memory.

Safe to run more than once.

    python scripts/maintenance/add_move_out_settlement_columns.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402

STATEMENTS = [
    "ALTER TABLE tenant_profiles ADD COLUMN IF NOT EXISTS moved_out_on DATE NULL",
    "ALTER TABLE unit_inventory_items ADD COLUMN IF NOT EXISTS "
    "replacement_cost NUMERIC(12,2) NOT NULL DEFAULT 0",
]


def main():
    app = create_app()
    with app.app_context():
        for stmt in STATEMENTS:
            db.session.execute(text(stmt))
            print("  ok:", stmt.split("IF NOT EXISTS")[-1].strip()[:70])
        db.session.commit()
        for table in ("tenant_profiles", "unit_inventory_items"):
            cols = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t ORDER BY ordinal_position"
            ), {"t": table}).scalars().all()
            print(f"\n{table}: {len(cols)} columns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
