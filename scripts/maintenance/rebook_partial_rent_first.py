"""Re-book move-in part payments that were split deposit-first.

The move-in split originally credited the security deposit first and left
the month open. It is the other way round: the rent is settled first and
whole, and only the deposit carries a balance. Reservations approved under
the old order therefore recorded the whole of a part payment as deposit and
left the first billing cycle unpaid — the tenant showed a month in arrears
on money that should have settled that month outright.

This rewrites those records. The original payment cannot be edited: its
amount and reference are both inside the hashed ledger payload, so changing
either would break every chained hash after it. It is voided instead —
payment_status is not part of the payload — and replaced with the two rows
the rent-first split would have written, for the same total, at the same
timestamp.

    python scripts/maintenance/rebook_partial_rent_first.py           # dry run
    python scripts/maintenance/rebook_partial_rent_first.py --apply
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from app.extensions import db
from app.models import (TenantProfile, Payment, Reservation,
                        PAYMENT_STATUSES_NOT_COUNTED)
from app.billing_utils import billing_month_for
from app.blueprints.admin.routes import _generate_payment_ledger, verify_blockchain_chain

APPLY = "--apply" in sys.argv


def candidates():
    """Tenancies whose first month is unbooked while a deposit row holds
    enough to have settled it."""
    out = []
    for profile in (db.session.query(TenantProfile)
                    .filter(TenantProfile.is_active.is_(True)).all()):
        if not profile.unit or not profile.contract_start:
            continue
        rent = float(profile.contract_rent or 0)
        if rent <= 0:
            continue
        cycle = billing_month_for(profile, profile.contract_start)
        rows = (db.session.query(Payment)
                .filter(Payment.tenant_profile_id == profile.id,
                        ~Payment.payment_status.in_(PAYMENT_STATUSES_NOT_COUNTED))
                .order_by(Payment.id).all())
        if any(p.payment_month == cycle and not p.is_deposit for p in rows):
            continue  # the month is already settled
        deposits = [p for p in rows if p.is_deposit
                    and p.deposit_transaction_type == "deposit_paid"]
        if len(deposits) != 1:
            continue  # more than one: not the single part payment this fixes
        row = deposits[0]
        if float(row.amount or 0) < rent - 0.005:
            continue  # never covered a whole month, so nothing to re-book
        out.append((profile, row, rent, cycle))
    return out


def main():
    app = create_app()
    with app.app_context():
        before = verify_blockchain_chain()
        print(f"blockchain before: valid={before['valid']} "
              f"ledgers={before['total_ledgers']} issues={len(before['issues'])}")

        found = candidates()
        if not found:
            print("Nothing to re-book.")
            return

        for profile, row, rent, cycle in found:
            code = profile.unit.unit_code
            total = float(row.amount or 0)
            deposit_part = total - rent
            print(f"\n{profile.user.full_name} — {code} ({profile.unit.type})")
            print(f"  void    #{row.id} ₱{total:,.2f} {row.reference!r} (month=None)")
            print(f"  write   ₱{rent:,.2f} Monthly - {code}  month={cycle}")
            if deposit_part > 0.005:
                print(f"  write   ₱{deposit_part:,.2f} Security Deposit - {code}  month=None")
            print(f"  total unchanged: ₱{total:,.2f}")

            if not APPLY:
                continue

            row.payment_status = "voided"
            row.notes = ((row.notes or "") + " — re-booked: the rent is settled "
                         "first, so this was split into the month's rent and "
                         "the deposit.").strip()
            fresh = [Payment(
                tenant_profile_id=profile.id, amount=rent,
                reference=f"Monthly - {code}",
                notes="First month's rent from the move-in payment",
                is_deposit=False, payment_month=cycle,
                payment_method=row.payment_method, paid_at=row.paid_at,
            )]
            if deposit_part > 0.005:
                fresh.append(Payment(
                    tenant_profile_id=profile.id, amount=deposit_part,
                    reference=f"Security Deposit - {code}",
                    notes="Part payment towards the security deposit",
                    is_deposit=True, deposit_transaction_type="deposit_paid",
                    payment_method=row.payment_method, paid_at=row.paid_at,
                ))
            for p in fresh:
                db.session.add(p)
            db.session.flush()
            for p in fresh:
                _generate_payment_ledger(p)

        if not APPLY:
            print("\nDRY RUN — nothing written. Re-run with --apply.")
            return

        db.session.commit()
        after = verify_blockchain_chain()
        print(f"\nblockchain after: valid={after['valid']} "
              f"ledgers={after['total_ledgers']} issues={len(after['issues'])}")
        for i in after["issues"][:5]:
            print(f"  ISSUE {i}")


if __name__ == "__main__":
    main()
