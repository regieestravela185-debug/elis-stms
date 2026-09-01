"""Give each tenant their own contracted monthly rent.

Rent used to be read live off Unit.price_monthly, so raising a unit's
asking price silently revalued what its current tenant already owed —
three unpaid months at ₱4,500 would become three unpaid months at the new
price. Rent is a term of the contract, not a live attribute of the unit.

Backfills every existing profile from its unit's current price, which is
what those tenants were already being charged, so nothing changes for
them today. From here on the figure is captured when the contract is
created and stops tracking the unit.

Safe to run more than once.

    python scripts/maintenance/add_tenant_monthly_rent.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402
from app.models import TenantProfile  # noqa: E402


def main():
    app = create_app()
    with app.app_context():
        db.session.execute(text(
            "ALTER TABLE tenant_profiles "
            "ADD COLUMN IF NOT EXISTS monthly_rent NUMERIC(12,2) NULL"
        ))
        db.session.commit()
        print("column monthly_rent ready")

        # Only fill profiles that have none. A profile whose rent was already
        # captured must keep it — that is the whole point of the column.
        filled = 0
        for p in db.session.query(TenantProfile).filter(
                TenantProfile.monthly_rent.is_(None)).all():
            unit = p.unit
            if not unit or not unit.price_monthly:
                print(f"  profile {p.id}: no unit price to copy — left NULL "
                      f"(contract_rent falls back to the unit)")
                continue
            p.monthly_rent = unit.price_monthly
            who = p.user.full_name if p.user else f"profile {p.id}"
            print(f"  {who} — unit {unit.unit_code}: ₱{float(unit.price_monthly):,.2f}")
            filled += 1

        if filled:
            db.session.commit()
            print(f"\nbackfilled {filled} profile(s).")
        else:
            db.session.rollback()
            print("\nnothing to backfill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
