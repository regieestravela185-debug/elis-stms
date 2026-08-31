#!/usr/bin/env python3
"""
Creates the utility_bills table — one per-tenant, per-month Electric+Water
bill for RESIDENTIAL tenants only (Buildings 1-4). Commercial tenants pay
electric/water directly to the utility company and are never billed here.

Safe to run multiple times (IF NOT EXISTS guards).
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Creating utility_bills table...")
    try:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS utility_bills (
                id SERIAL PRIMARY KEY,
                tenant_profile_id INTEGER NOT NULL REFERENCES tenant_profiles(id),
                billing_month VARCHAR(7) NOT NULL,
                electric_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                water_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                rent_amount_snapshot NUMERIC(12,2) NOT NULL DEFAULT 0,
                carried_over_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                due_date DATE NOT NULL,
                is_paid BOOLEAN NOT NULL DEFAULT FALSE,
                paid_at TIMESTAMP NULL,
                marked_paid_by INTEGER NULL REFERENCES users(id),
                reminder_sent_at DATE NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (tenant_profile_id, billing_month)
            )
        """))
        db.session.execute(db.text(
            "CREATE INDEX IF NOT EXISTS idx_utility_bills_tenant ON utility_bills(tenant_profile_id)"
        ))
        db.session.execute(db.text(
            "CREATE INDEX IF NOT EXISTS idx_utility_bills_month ON utility_bills(billing_month)"
        ))
        db.session.commit()
        print("   Done.")
    except Exception as e:
        db.session.rollback()
        print(f"   Error: {e}")
        raise

    print("\nMigration complete.")
