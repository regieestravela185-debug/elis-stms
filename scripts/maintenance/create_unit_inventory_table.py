"""Create unit_inventory_items and seed the standard rows.

The Kasunduan printed its "MGA GAMIT NA NASA LOOB NG UNIT" table blank
for the parties to fill in by hand, so the system held none of it. This
gives every residential unit the seventeen standard rows at quantity 0,
ready for the administrator to encode. Commercial units are skipped —
the fixture list is the residential Kasunduan's.

Quantity starts at 0 rather than a guess: an un-encoded unit should read
as "not yet inventoried", not as a unit that genuinely has none.

Safe to run more than once.

    python scripts/maintenance/create_unit_inventory_table.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402
from app.inventory import STANDARD_UNIT_INVENTORY, ensure_unit_inventory  # noqa: E402
from app.models import Unit  # noqa: E402

CREATE = """
CREATE TABLE IF NOT EXISTS unit_inventory_items (
    id SERIAL PRIMARY KEY,
    unit_id INTEGER NOT NULL REFERENCES units(id),
    label VARCHAR(120) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    condition VARCHAR(20) NOT NULL DEFAULT 'good',
    notes VARCHAR(255) NULL,
    sort_order INTEGER NOT NULL DEFAULT 999,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (unit_id, label)
);
"""
INDEX = ("CREATE INDEX IF NOT EXISTS idx_unit_inventory_unit "
         "ON unit_inventory_items(unit_id)")


def main():
    app = create_app()
    with app.app_context():
        db.session.execute(text(CREATE))
        db.session.execute(text(INDEX))
        db.session.commit()
        print(f"unit_inventory_items ready ({len(STANDARD_UNIT_INVENTORY)} standard items)")

        units = db.session.query(Unit).filter(Unit.type == "residential").all()
        seeded = 0
        for unit in units:
            before = db.session.execute(
                text("SELECT COUNT(*) FROM unit_inventory_items WHERE unit_id = :u"),
                {"u": unit.id},
            ).scalar()
            ensure_unit_inventory(unit)
            after = db.session.execute(
                text("SELECT COUNT(*) FROM unit_inventory_items WHERE unit_id = :u"),
                {"u": unit.id},
            ).scalar()
            if after > before:
                print(f"  {unit.unit_code}: seeded {after - before} row(s)")
                seeded += 1
            else:
                print(f"  {unit.unit_code}: already has {before} row(s)")
        db.session.commit()

        total = db.session.execute(
            text("SELECT COUNT(*) FROM unit_inventory_items")).scalar()
        print(f"\n{len(units)} residential unit(s), {seeded} newly seeded, "
              f"{total} inventory rows in total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
