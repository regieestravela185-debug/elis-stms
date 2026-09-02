"""Remove utility bills raised for a tenant's move-in month.

Utilities begin the month AFTER move-in — a tenant's first month's
consumption is not metered separately from the outgoing tenant's, so
there is nothing to charge them for. The billing page created a row for
every active tenant regardless, so tenants were billed a month early.

Only bills for a month before the tenant's first billable one are
touched. A bill already marked settled is left alone by default, because
deleting one would take a payment out of the tenant's history — those are
reported instead, for a person to look at.

Removing a bill also rewinds what it carried into the following month,
since that charge came from a month that should never have been billed.

Pass --force to remove settled ones too. Use it only where the settled
state came from the cascade migration rather than a real payment — read
the dry run first.

    python scripts/maintenance/remove_move_in_month_utility_bills.py [--dry-run] [--force]
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app import create_app, db  # noqa: E402
from app.billing_utils import first_utility_month  # noqa: E402
from app.models import UtilityBill  # noqa: E402


def _rewind_carry_over(bill):
    """Take this bill's charges back out of the next month's carry-over.

    The following month inherited whatever this one left unpaid. If this
    month should never have been billed, that inheritance is wrong too,
    and leaving it would keep charging for a bill that no longer exists.
    """
    following = (db.session.query(UtilityBill)
                 .filter(UtilityBill.tenant_profile_id == bill.tenant_profile_id,
                         UtilityBill.billing_month > bill.billing_month)
                 .order_by(UtilityBill.billing_month)
                 .first())
    if not following:
        return None
    before = (float(following.carried_over_electric or 0),
              float(following.carried_over_water or 0))
    following.carried_over_electric = max(
        0.0, before[0] - bill.electric_outstanding - float(bill.electric_amount or 0))
    following.carried_over_water = max(
        0.0, before[1] - bill.water_outstanding - float(bill.water_amount or 0))
    following.sync_totals()
    return (following, before)


def main(dry_run=False, force=False):
    app = create_app()
    with app.app_context():
        removed, kept = 0, 0
        for bill in (db.session.query(UtilityBill)
                     .order_by(UtilityBill.tenant_profile_id,
                               UtilityBill.billing_month).all()):
            profile = bill.tenant_profile
            first = first_utility_month(profile) if profile else None
            if not first or bill.billing_month >= first:
                continue

            who = profile.user.full_name if profile and profile.user else "?"
            desc = (f"{who} {bill.billing_month} "
                    f"(electric ₱{float(bill.electric_amount):,.2f}, "
                    f"water ₱{float(bill.water_amount):,.2f})")

            carried = (float(bill.carried_over_electric or 0)
                       + float(bill.carried_over_water or 0))
            settled = bill.electric_paid or bill.water_paid
            if settled and not force:
                print(f"  KEPT    {desc} — settled already; "
                      f"re-run with --force if that came from the cascade "
                      f"migration rather than a real payment")
                kept += 1
                continue
            if carried and not force:
                print(f"  KEPT    {desc} — carries ₱{carried:,.2f} from an "
                      f"earlier month; left for review")
                kept += 1
                continue

            rewound = _rewind_carry_over(bill)
            print(f"  REMOVED {desc} — before their first billable month ({first})"
                  + ("  [settled state overridden by --force]" if settled else ""))
            if rewound:
                nxt, before = rewound
                print(f"          {nxt.billing_month} carry-over rewound: "
                      f"electric ₱{before[0]:,.2f} -> ₱{float(nxt.carried_over_electric):,.2f}, "
                      f"water ₱{before[1]:,.2f} -> ₱{float(nxt.carried_over_water):,.2f}")
            db.session.delete(bill)
            removed += 1

        print(f"\nremoved {removed}, kept for review {kept}.")
        if dry_run:
            db.session.rollback()
            print("--dry-run: rolled back, nothing written.")
        elif removed:
            db.session.commit()
            print("Committed.")
        else:
            db.session.rollback()
            print("Nothing to remove.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv,
                          force="--force" in sys.argv))
