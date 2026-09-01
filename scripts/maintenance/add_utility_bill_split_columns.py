"""Add per-component settlement to utility_bills.

Electric and water used to be settled together through a single is_paid
flag, with one lumped carried_over_amount. Tenants settle them
independently in practice — paying the electric and leaving the water —
so each component now has its own paid flag and its own carry-over
bucket. Also adds the reminder pause used when a tenant tells the
administrator they will settle next month.

Safe to run more than once. Run against the same database the app uses:

    python scripts/maintenance/add_utility_bill_split_columns.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402

STATEMENTS = [
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS carried_over_electric NUMERIC(12,2) NOT NULL DEFAULT 0",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS carried_over_water NUMERIC(12,2) NOT NULL DEFAULT 0",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS electric_paid BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS electric_paid_at TIMESTAMP NULL",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS water_paid BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS water_paid_at TIMESTAMP NULL",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS reminders_paused BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS reminders_paused_at TIMESTAMP NULL",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS reminders_paused_by INTEGER NULL REFERENCES users(id)",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS reminders_paused_note VARCHAR(255) NULL",
]

# Rows written before this migration carried one lumped figure and one
# paid flag. Split the lump onto the electric bucket (it cannot be
# attributed retroactively) and mirror the old flag onto both components
# so nothing that was already settled reopens.
BACKFILL = [
    """UPDATE utility_bills
          SET carried_over_electric = carried_over_amount
        WHERE carried_over_amount > 0
          AND carried_over_electric = 0
          AND carried_over_water = 0""",
    """UPDATE utility_bills
          SET electric_paid = TRUE,
              water_paid = TRUE,
              electric_paid_at = COALESCE(electric_paid_at, paid_at),
              water_paid_at = COALESCE(water_paid_at, paid_at)
        WHERE is_paid = TRUE
          AND (electric_paid = FALSE OR water_paid = FALSE)""",
]


def main():
    app = create_app()
    with app.app_context():
        exists = db.session.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'utility_bills'"
        )).first()
        if not exists:
            print("utility_bills does not exist yet — run "
                  "create_utility_bills_table.py first.")
            return 1

        for stmt in STATEMENTS:
            db.session.execute(text(stmt))
            print("  ok:", stmt.split("IF NOT EXISTS")[-1].strip()[:60])
        db.session.commit()

        for stmt in BACKFILL:
            result = db.session.execute(text(stmt))
            print(f"  backfilled {result.rowcount} row(s)")
        db.session.commit()

        cols = db.session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'utility_bills' ORDER BY ordinal_position"
        )).scalars().all()
        print("\nutility_bills now has", len(cols), "columns:")
        print("  " + ", ".join(cols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
