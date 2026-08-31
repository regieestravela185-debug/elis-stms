from __future__ import annotations

import calendar
from datetime import date

from .extensions import db
from .models import TenantProfile, UtilityBill
from .ai_utils import compute_water_bill


def _prev_billing_month(billing_month: str) -> str:
    """"YYYY-MM" -> the "YYYY-MM" string for the month before it."""
    year, month = (int(x) for x in billing_month.split("-"))
    month -= 1
    if month == 0:
        month = 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def get_or_create_utility_bill(tenant_profile: TenantProfile, billing_month: str) -> UtilityBill:
    """Idempotent. Returns the existing UtilityBill for tenant+month if
    present, else creates it: due_date anchored to contract_start.day
    (clamped to the billing month's length, same convention used
    throughout app/jobs.py and admin/routes.py for rent due dates),
    water_amount defaulted from compute_water_bill(unit.pax_range),
    electric_amount 0 (admin fills in), rent_amount_snapshot from
    unit.price_monthly, and carried_over_amount = the prior month's
    total_due if that bill exists and is_paid is False, else 0.

    Carry-over compounds automatically — a bill left unpaid for several
    months in a row keeps inheriting the growing total on each
    subsequent month's bill, by design (utilities have no late penalty,
    unlike rent; an unpaid balance just rolls forward).

    Does not commit — the caller controls the transaction (the admin
    bulk-input page commits once after creating a whole page of rows;
    the reminder job commits once after its whole pass).
    """
    existing = (
        db.session.query(UtilityBill)
        .filter(
            UtilityBill.tenant_profile_id == tenant_profile.id,
            UtilityBill.billing_month == billing_month,
        )
        .first()
    )
    if existing:
        return existing

    year, month = (int(x) for x in billing_month.split("-"))
    due_day = 1
    if tenant_profile.contract_start:
        due_day = min(tenant_profile.contract_start.day, calendar.monthrange(year, month)[1])
    due_date = date(year, month, due_day)

    unit = tenant_profile.unit
    water_amount = compute_water_bill(unit.pax_range) if unit else None
    rent_amount = float(unit.price_monthly) if unit and unit.price_monthly else 0

    prior_bill = (
        db.session.query(UtilityBill)
        .filter(
            UtilityBill.tenant_profile_id == tenant_profile.id,
            UtilityBill.billing_month == _prev_billing_month(billing_month),
        )
        .first()
    )
    carried_over = prior_bill.total_due if prior_bill and not prior_bill.is_paid else 0

    bill = UtilityBill(
        tenant_profile_id=tenant_profile.id,
        billing_month=billing_month,
        electric_amount=0,
        water_amount=water_amount or 0,
        rent_amount_snapshot=rent_amount,
        carried_over_amount=carried_over,
        due_date=due_date,
    )
    db.session.add(bill)
    db.session.flush()  # assign bill.id without committing the whole transaction
    return bill
