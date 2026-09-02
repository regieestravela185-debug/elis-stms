"""Tag rent payments that were recorded without a billing cycle.

payment_month is what every arrears and outstanding check matches on. A
rent payment saved without it counts as revenue but settles no month, so
the tenant reads as unpaid for a month they have in fact paid — which is
what happened to every first-month payment created on reservation
approval, since that code never set it.

The cycle is derived from when the payment was made, using the contract's
anniversary day: a payment belongs to the most recent cycle whose due
date had already arrived. Deposits are skipped — they are not rent and
settle no month.

A payment that already carries a cycle is never rewritten, and one dated
before the contract began is reported rather than guessed at.

Pass --dry-run to see the changes without writing.

    python scripts/maintenance/backfill_payment_months.py [--dry-run]
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app import create_app, db  # noqa: E402
from app.billing_utils import billing_month_for  # noqa: E402
from app.models import Payment  # noqa: E402


def main(dry_run=False):
    app = create_app()
    with app.app_context():
        untagged = (
            db.session.query(Payment)
            .filter(Payment.payment_month.is_(None),
                    Payment.is_deposit.is_(False))
            .order_by(Payment.tenant_profile_id, Payment.paid_at)
            .all()
        )
        if not untagged:
            print("Every rent payment already carries a billing cycle.")
            return 0

        tagged, skipped, conflicts = 0, 0, 0
        for pay in untagged:
            profile = pay.tenant_profile
            who = profile.user.full_name if profile and profile.user else f"profile {pay.tenant_profile_id}"
            cycle = billing_month_for(profile, pay.paid_at.date()) if profile else None

            if not cycle:
                print(f"  #{pay.id} {who} ₱{float(pay.amount):,.2f} paid "
                      f"{pay.paid_at.date()} — before the contract began, left untagged")
                skipped += 1
                continue

            clash = (db.session.query(Payment)
                     .filter(Payment.tenant_profile_id == pay.tenant_profile_id,
                             Payment.payment_month == cycle,
                             Payment.is_deposit.is_(False),
                             Payment.id != pay.id)
                     .first())
            if clash:
                print(f"  #{pay.id} {who} ₱{float(pay.amount):,.2f} → {cycle} "
                      f"SKIPPED — payment #{clash.id} already covers that cycle")
                conflicts += 1
                continue

            print(f"  #{pay.id} {who} ₱{float(pay.amount):,.2f} paid "
                  f"{pay.paid_at.date()} → cycle {cycle}   ({pay.notes or pay.reference or ''})")
            pay.payment_month = cycle
            tagged += 1

        print(f"\ntagged: {tagged}   before contract: {skipped}   "
              f"cycle already covered: {conflicts}")

        if dry_run:
            db.session.rollback()
            print("--dry-run: rolled back, nothing written.")
        elif tagged:
            db.session.commit()
            print("Committed.")
        else:
            db.session.rollback()
            print("Nothing to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))
