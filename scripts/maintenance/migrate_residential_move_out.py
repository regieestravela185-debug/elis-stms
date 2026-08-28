#!/usr/bin/env python3
"""
Schema changes to support residential month-to-month tenancy (no fixed
move-out date) with a formal Move-Out Notice flow:

1. Create move_out_notices table.
2. Add tenant_profiles.dismissed_outstanding_month (per-tenant "Outstanding
   This Month" dismissal).
3. Make reservations.move_out_date nullable (residential reservations no
   longer collect a move-out date; commercial still does).

Safe to run multiple times (IF NOT EXISTS / conditional guards).
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("1) Creating move_out_notices table...")
    try:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS move_out_notices (
                id SERIAL PRIMARY KEY,
                tenant_profile_id INTEGER NOT NULL REFERENCES tenant_profiles(id),
                original_move_out_date DATE NOT NULL,
                planned_move_out_date DATE NOT NULL,
                notes TEXT NULL,
                admin_response TEXT NULL,
                admin_response_at TIMESTAMP NULL,
                admin_response_by INTEGER NULL REFERENCES users(id),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        db.session.execute(db.text(
            "CREATE INDEX IF NOT EXISTS ix_move_out_notices_tenant_profile_id "
            "ON move_out_notices (tenant_profile_id)"
        ))
        db.session.commit()
        print("   Done.")
    except Exception as e:
        db.session.rollback()
        print(f"   Error: {e}")
        raise

    print("2) Adding tenant_profiles.dismissed_outstanding_month...")
    try:
        db.session.execute(db.text("""
            ALTER TABLE tenant_profiles
            ADD COLUMN IF NOT EXISTS dismissed_outstanding_month VARCHAR(7) NULL
        """))
        db.session.commit()
        print("   Done.")
    except Exception as e:
        db.session.rollback()
        print(f"   Error: {e}")
        raise

    print("3) Making reservations.move_out_date nullable...")
    try:
        db.session.execute(db.text("""
            ALTER TABLE reservations
            ALTER COLUMN move_out_date DROP NOT NULL
        """))
        db.session.commit()
        print("   Done.")
    except Exception as e:
        db.session.rollback()
        print(f"   Error: {e}")
        raise

    print("\nAll migrations complete.")
