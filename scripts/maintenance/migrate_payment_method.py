#!/usr/bin/env python3
"""
Add payment_method column to payments table — lets a payment record say
whether it was Cash, Bank Transfer, or Other, so the tenant sees the right
label regardless of whether admin entered it manually or the tenant
self-reported a bank transfer.

Safe to run multiple times (IF NOT EXISTS guards).
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Adding payment_method column to payments table...")
    try:
        db.session.execute(db.text("""
            ALTER TABLE payments
            ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20) NULL
        """))
        db.session.commit()
        print("Done.")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        raise
