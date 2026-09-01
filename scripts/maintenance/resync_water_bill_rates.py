"""Re-apply the water bracket rates to existing bills, then rebuild the
carry-over chain that follows from them.

Water is a fixed charge per occupancy bracket, not a metered reading, so
a bill's water figure should always equal the rate for its unit's
pax_range. When the rates are corrected, bills already written keep the
old figure — this brings them back in line.

Two rules:

  * A settled component is never touched. If the tenant has already paid
    that water charge, the amount they paid stands.
  * Carry-over is recomputed forward per tenant after the amounts are
    fixed, because each month's carry-over is derived from the previous
    month's outstanding. Changing an early month's water without
    rebuilding the chain would leave every later month wrong.

Prints every change. Pass --dry-run to see them without writing.

    python scripts/maintenance/resync_water_bill_rates.py [--dry-run]
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app import create_app, db  # noqa: E402
from app.ai_utils import compute_water_bill  # noqa: E402
from app.models import UtilityBill  # noqa: E402


def main(dry_run=False):
    app = create_app()
    with app.app_context():
        bills = (
            db.session.query(UtilityBill)
            .order_by(UtilityBill.tenant_profile_id, UtilityBill.billing_month)
            .all()
        )
        if not bills:
            print("No utility bills exist yet — nothing to resync.")
            return 0

        by_tenant = {}
        for b in bills:
            by_tenant.setdefault(b.tenant_profile_id, []).append(b)

        amount_changes, carry_changes, skipped = 0, 0, 0

        for tenant_id, tenant_bills in by_tenant.items():
            profile = tenant_bills[0].tenant_profile
            unit = profile.unit if profile else None
            who = profile.user.full_name if profile and profile.user else f"profile {tenant_id}"
            expected = compute_water_bill(unit.pax_range) if unit else None

            print(f"\n{who} — unit {unit.unit_code if unit else '?'} "
                  f"({unit.pax_range if unit else 'no pax_range'} pax "
                  f"→ ₱{expected:,.2f})" if expected is not None
                  else f"\n{who} — no water rate for this unit, skipping amounts")

            prev = None
            for b in tenant_bills:
                # 1. bring the water amount back to its bracket rate
                current = float(b.water_amount or 0)
                if expected is None:
                    pass
                elif b.water_paid:
                    if abs(current - expected) > 0.005:
                        print(f"    {b.billing_month}  water ₱{current:,.2f} "
                              f"left as is — already settled")
                        skipped += 1
                elif abs(current - expected) > 0.005:
                    print(f"    {b.billing_month}  water ₱{current:,.2f} "
                          f"→ ₱{expected:,.2f}")
                    b.water_amount = expected
                    amount_changes += 1

                # 2. rebuild this month's carry-over from last month's
                #    outstanding, now that the amounts are correct
                want_e = prev.electric_outstanding if prev else 0.0
                want_w = prev.water_outstanding if prev else 0.0
                have_e = float(b.carried_over_electric or 0)
                have_w = float(b.carried_over_water or 0)
                if abs(have_e - want_e) > 0.005 or abs(have_w - want_w) > 0.005:
                    print(f"    {b.billing_month}  carry-over "
                          f"E ₱{have_e:,.2f}/W ₱{have_w:,.2f} → "
                          f"E ₱{want_e:,.2f}/W ₱{want_w:,.2f}")
                    b.carried_over_electric = want_e
                    b.carried_over_water = want_w
                    carry_changes += 1

                b.sync_totals()
                prev = b

        print(f"\nwater amounts corrected: {amount_changes}")
        print(f"carry-overs rebuilt:     {carry_changes}")
        print(f"left alone (settled):    {skipped}")

        if dry_run:
            db.session.rollback()
            print("\n--dry-run: rolled back, nothing written.")
        elif amount_changes or carry_changes:
            db.session.commit()
            print("\nCommitted.")
        else:
            db.session.rollback()
            print("\nEverything already matches the current rates — no write needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))
