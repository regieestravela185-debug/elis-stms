#!/usr/bin/env python3
"""
Adds the columns that let a reservation be paid in instalments, and that
record which reservation won a contested unit.

    amount_paid        what the tenant has handed over so far against the
                       move-in total (security deposit + first month's rent)
    first_paid_at      when the first peso landed. A unit goes to whoever
                       pays first, not whoever booked first, so this is the
                       field that settles a contested unit.
    fully_paid_at      when the balance was cleared
    superseded_by_id   on a reservation that lost the race, the one that won

Existing rows get amount_paid = 0. Reservations approved before instalments
existed carry no payment rows of their own, and approve_reservation treats a
zero there as "settled in full", which is how those reservations behaved.

Safe to run multiple times (IF NOT EXISTS guard).
"""

from app import create_app
from app.extensions import db

app = create_app()

STATEMENTS = [
    ("reservations.amount_paid", """
        ALTER TABLE reservations
        ADD COLUMN IF NOT EXISTS amount_paid NUMERIC(12,2) NOT NULL DEFAULT 0
    """),
    ("reservations.first_paid_at", """
        ALTER TABLE reservations
        ADD COLUMN IF NOT EXISTS first_paid_at TIMESTAMP NULL
    """),
    ("reservations.fully_paid_at", """
        ALTER TABLE reservations
        ADD COLUMN IF NOT EXISTS fully_paid_at TIMESTAMP NULL
    """),
    ("reservations.superseded_by_id", """
        ALTER TABLE reservations
        ADD COLUMN IF NOT EXISTS superseded_by_id INTEGER NULL
            REFERENCES reservations(id)
    """),
]

with app.app_context():
    for label, sql in STATEMENTS:
        print(f"Adding {label}...")
        try:
            db.session.execute(db.text(sql))
            db.session.commit()
            print("   Done.")
        except Exception as e:
            db.session.rollback()
            print(f"   Error: {e}")
            raise

    print("\nMigration complete.")
