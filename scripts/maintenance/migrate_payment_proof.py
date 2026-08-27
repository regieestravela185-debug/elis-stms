#!/usr/bin/env python3
"""
Add proof_file column to payments table — lets a tenant self-report a bank
transfer payment with an uploaded receipt/screenshot, which admin then
reviews (payment_status='pending' until approved or rejected).

Safe to run multiple times (IF NOT EXISTS guards).
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Adding proof_file column to payments table...")
    try:
        db.session.execute(db.text("""
            ALTER TABLE payments
            ADD COLUMN IF NOT EXISTS proof_file VARCHAR(500) NULL
        """))
        db.session.commit()
        print("Done.")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        raise
