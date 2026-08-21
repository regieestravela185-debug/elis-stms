#!/usr/bin/env python3
"""
One-time backfill: compute is_late for existing rent payments.

The is_late column always defaulted to False and nothing ever set it, so
every tenant's predictive payment-risk profile came out "low risk"
regardless of actual behavior. This recomputes is_late for historical
payments using the same due-day convention already used elsewhere in the
app (tenant/routes.py "next payment due"): rent is due monthly on the same
day-of-month as the tenant's contract_start.

Skipped:
  - deposit payments/returns (is_deposit=True) — not rent
  - each tenant's very first (move-in) payment — paid at approval time,
    not tied to a recurring billing cycle, so it can't be "late"

Usage:
    .venv/bin/python scripts/maintenance/backfill_payment_is_late.py            # apply
    .venv/bin/python scripts/maintenance/backfill_payment_is_late.py --dry-run  # preview only
"""
from __future__ import annotations

import calendar
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import create_app
from app.extensions import db
from app.models import Payment, TenantProfile

DRY_RUN = "--dry-run" in sys.argv


def due_date_for(profile: TenantProfile, paid_at) -> date | None:
    if not profile.contract_start:
        return None
    day = min(profile.contract_start.day, calendar.monthrange(paid_at.year, paid_at.month)[1])
    return date(paid_at.year, paid_at.month, day)


def main() -> None:
    app = create_app()
    with app.app_context():
        profiles = {p.id: p for p in db.session.query(TenantProfile).all()}

        # Earliest payment per tenant = move-in payment, never "late".
        first_payment_id = {}
        for p in (
            db.session.query(Payment)
            .filter(Payment.is_deposit == False)  # noqa: E712
            .order_by(Payment.tenant_profile_id, Payment.paid_at.asc(), Payment.id.asc())
            .all()
        ):
            first_payment_id.setdefault(p.tenant_profile_id, p.id)

        payments = (
            db.session.query(Payment)
            .filter(Payment.is_deposit == False)  # noqa: E712
            .all()
        )

        changed = 0
        skipped_no_contract = 0
        for p in payments:
            if p.id == first_payment_id.get(p.tenant_profile_id):
                continue

            profile = profiles.get(p.tenant_profile_id)
            if not profile:
                continue

            due = due_date_for(profile, p.paid_at)
            if due is None:
                skipped_no_contract += 1
                continue

            new_is_late = p.paid_at.date() > due
            if new_is_late != p.is_late:
                changed += 1
                print(
                    f"  payment #{p.id} (tenant {p.tenant_profile_id}, paid {p.paid_at.date()}, "
                    f"due {due}): is_late {p.is_late} -> {new_is_late}"
                )
                if not DRY_RUN:
                    p.is_late = new_is_late
                    if new_is_late:
                        p.payment_status = "late"

        if not DRY_RUN:
            db.session.commit()

        print(f"\n{'[DRY RUN] Would update' if DRY_RUN else 'Updated'} {changed} of {len(payments)} rent payments.")
        if skipped_no_contract:
            print(f"Skipped {skipped_no_contract} payment(s) — tenant has no contract_start.")


if __name__ == "__main__":
    main()
