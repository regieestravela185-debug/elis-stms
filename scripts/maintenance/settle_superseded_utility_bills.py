"""Close earlier utility bills whose balance a later, settled bill carried.

Each month's bill carries forward whatever the month before left unpaid,
so settling a component on a later bill settles every earlier month of
it. Marking only the later bill left the earlier ones reading unpaid, and
anything summing across bills counted the same peso once for each month
it had rolled through — the dashboard reported utilities overdue for a
tenant who owed nothing.

Only components already settled on a LATER bill are closed here. A month
genuinely still unpaid is left exactly as it is.

Pass --dry-run to see the changes without writing.

    python scripts/maintenance/settle_superseded_utility_bills.py [--dry-run]
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app import create_app, db  # noqa: E402
from app.models import UtilityBill  # noqa: E402


def main(dry_run=False):
    app = create_app()
    with app.app_context():
        bills = (db.session.query(UtilityBill)
                 .order_by(UtilityBill.tenant_profile_id,
                           UtilityBill.billing_month)
                 .all())
        by_tenant = {}
        for b in bills:
            by_tenant.setdefault(b.tenant_profile_id, []).append(b)

        closed = 0
        for tenant_id, rows in by_tenant.items():
            profile = rows[0].tenant_profile
            who = profile.user.full_name if profile and profile.user else f"profile {tenant_id}"
            for field in ("electric", "water"):
                # Walk newest first; once a settled month is seen, every
                # earlier one it carried is settled too.
                seen_settled = False
                for b in reversed(rows):
                    if getattr(b, f"{field}_paid"):
                        seen_settled = True
                        continue
                    if seen_settled:
                        print(f"  {who} {b.billing_month} {field}: "
                              f"₱{getattr(b, field + '_due'):,.2f} — carried into a "
                              f"later bill that is settled, closing")
                        setattr(b, f"{field}_paid", True)
                        b.sync_totals()
                        closed += 1

        print(f"\nclosed {closed} superseded component(s).")
        if dry_run:
            db.session.rollback()
            print("--dry-run: rolled back, nothing written.")
        elif closed:
            db.session.commit()
            print("Committed.")
        else:
            db.session.rollback()
            print("Nothing to close.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))
