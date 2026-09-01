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
    unit.price_monthly, and the two carry-over buckets taken from
    whichever of the prior month's components were left unsettled.

    Carry-over is per component, because tenants settle electric and
    water independently: if last month's electric was paid and its water
    was not, only the water rolls forward. It compounds automatically —
    a component left unpaid for several months keeps inheriting its own
    growing balance, by design (utilities have no late penalty, unlike
    rent; an unpaid balance just rolls forward).

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
    carried_electric = prior_bill.electric_outstanding if prior_bill else 0
    carried_water = prior_bill.water_outstanding if prior_bill else 0

    bill = UtilityBill(
        tenant_profile_id=tenant_profile.id,
        billing_month=billing_month,
        electric_amount=0,
        water_amount=water_amount or 0,
        rent_amount_snapshot=rent_amount,
        carried_over_electric=carried_electric,
        carried_over_water=carried_water,
        due_date=due_date,
    )
    bill.sync_totals()
    db.session.add(bill)
    db.session.flush()  # assign bill.id without committing the whole transaction
    return bill


def _month_add(billing_month: str, delta: int) -> str:
    """"YYYY-MM" shifted by delta months."""
    year, month = (int(x) for x in billing_month.split("-"))
    index = year * 12 + (month - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def get_unpaid_rent_months(tenant_profile: TenantProfile, as_of: date | None = None):
    """Every billing month from the contract start up to the current cycle
    that has no recorded rent payment, oldest first.

    A month counts as settled when a non-deposit Payment carries that
    payment_month and has not been rejected. Deposits are excluded — they
    are not rent. Months whose due date has not arrived yet are excluded
    too, so a tenant is never shown as owing the month they are still in
    before it falls due.

    Rent arrears live here rather than on UtilityBill because rent
    collection stays entirely in Payment/PaymentLedger; UtilityBill only
    snapshots the rent figure for display alongside the utilities.
    """
    from .models import Payment, PAYMENT_STATUSES_NOT_COUNTED  # local: avoids a cycle

    as_of = as_of or date.today()
    start = tenant_profile.contract_start
    if not start:
        return []

    end = tenant_profile.contract_end
    last = as_of if not end or end > as_of else end

    paid_months = {
        m for (m,) in db.session.query(Payment.payment_month)
        .filter(
            Payment.tenant_profile_id == tenant_profile.id,
            Payment.payment_month.isnot(None),
            Payment.is_deposit.is_(False),
            Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED),
        )
        .all()
    }

    months, cursor = [], f"{start.year:04d}-{start.month:02d}"
    limit = f"{last.year:04d}-{last.month:02d}"
    while cursor <= limit:
        year, month = (int(x) for x in cursor.split("-"))
        due_day = min(start.day, calendar.monthrange(year, month)[1])
        if date(year, month, due_day) <= as_of and cursor not in paid_months:
            months.append(cursor)
        cursor = _month_add(cursor, 1)
    return months


def get_rent_arrears(tenant_profile: TenantProfile, as_of: date | None = None) -> dict:
    """Summary of what the tenant still owes in rent.

    Returns months (oldest first), their count, the monthly rate, and the
    total. Every unpaid month is valued at the unit's current
    price_monthly — the system keeps no history of past rates, so a rate
    change would revalue older months. Flagged here rather than silently
    assumed.
    """
    months = get_unpaid_rent_months(tenant_profile, as_of)
    unit = tenant_profile.unit
    rate = float(unit.price_monthly) if unit and unit.price_monthly else 0.0
    return {
        "months": months,
        "count": len(months),
        "monthly_rate": rate,
        "total": round(rate * len(months), 2),
        "oldest": months[0] if months else None,
    }
