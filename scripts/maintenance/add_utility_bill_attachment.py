"""Add the electricity bill attachment to utility_bills.

A submetered unit's electricity charge is a share of one Meralco bill, so
a tenant asking "why is mine this high" can only be answered by showing
the bill. That used to be a photo sent over Messenger, which left no
record beside the charge. These columns hold the uploaded bill and an
optional note from the administrator explaining the reading.

Safe to run more than once. Run against the same database the app uses:

    python scripts/maintenance/add_utility_bill_attachment.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402

STATEMENTS = [
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS electric_bill_path VARCHAR(500) NULL",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS electric_bill_name VARCHAR(255) NULL",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS electric_bill_uploaded_at TIMESTAMP NULL",
    "ALTER TABLE utility_bills ADD COLUMN IF NOT EXISTS electric_note VARCHAR(500) NULL",
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

        cols = db.session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'utility_bills' ORDER BY ordinal_position"
        )).scalars().all()
        print("\nutility_bills now has", len(cols), "columns:")
        print("  " + ", ".join(cols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
