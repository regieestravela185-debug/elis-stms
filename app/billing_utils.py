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
    the tenant's contract rent, and the two carry-over buckets taken from
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
    rent_amount = tenant_profile.contract_rent

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
    total. Unpaid months are valued at the tenant's own contract rent, so
    raising the unit's asking price for future tenants never revalues what
    someone already owes.
    """
    months = get_unpaid_rent_months(tenant_profile, as_of)
    rate = tenant_profile.contract_rent
    return {
        "months": months,
        "count": len(months),
        "monthly_rate": rate,
        "total": round(rate * len(months), 2),
        "oldest": months[0] if months else None,
    }


def get_payment_timeline(tenant_profile: TenantProfile, as_of: date | None = None):
    """Month-by-month record of what this tenant owed and what they paid,
    newest first, from their move-in to the current cycle.

    This is the view that answers "they have not paid since September" —
    a question the data could always answer but nothing ever displayed.
    Each row carries the rent status for that month and, for residential
    tenants, the electric and water status alongside it, because those
    settle separately.

    Months whose due date has not yet arrived are marked upcoming rather
    than unpaid, so a tenant is never shown as delinquent for the month
    they are still living through.
    """
    from .models import Payment, UtilityBill, PAYMENT_STATUSES_NOT_COUNTED

    as_of = as_of or date.today()
    start = tenant_profile.contract_start
    if not start:
        return []

    end = tenant_profile.contract_end
    last = as_of if not end or end > as_of else end
    rate = tenant_profile.contract_rent

    payments = {}
    for p in (db.session.query(Payment)
              .filter(Payment.tenant_profile_id == tenant_profile.id,
                      Payment.payment_month.isnot(None),
                      Payment.is_deposit.is_(False),
                      Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED))
              .order_by(Payment.paid_at.asc())
              .all()):
        payments[p.payment_month] = p

    bills = {b.billing_month: b for b in
             db.session.query(UtilityBill)
             .filter(UtilityBill.tenant_profile_id == tenant_profile.id)
             .all()}

    rows, cursor = [], f"{start.year:04d}-{start.month:02d}"
    limit = f"{last.year:04d}-{last.month:02d}"
    while cursor <= limit:
        year, month = (int(x) for x in cursor.split("-"))
        due = date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
        paid = payments.get(cursor)
        bill = bills.get(cursor)

        if paid:
            rent_state = "late" if paid.is_late else "paid"
        elif due > as_of:
            rent_state = "upcoming"
        else:
            rent_state = "unpaid"

        rows.append({
            "month": cursor,
            "label": date(year, month, 1).strftime("%B %Y"),
            "due_date": due,
            "rent_state": rent_state,
            "rent_amount": rate,
            "paid_on": paid.paid_at.date() if paid else None,
            "paid_amount": float(paid.amount) if paid else None,
            "method": paid.payment_method if paid else None,
            "bill": bill,
        })
        cursor = _month_add(cursor, 1)

    rows.reverse()  # newest first — the months in dispute are the recent ones
    return rows


def payment_standing(tenant_profile: TenantProfile, as_of: date | None = None) -> dict:
    """One-line standing for a monitoring row: how far behind, since when,
    and whether utilities are outstanding too."""
    from .models import UtilityBill

    arrears = get_rent_arrears(tenant_profile, as_of)
    utility_outstanding = sum(
        b.total_outstanding for b in
        db.session.query(UtilityBill)
        .filter(UtilityBill.tenant_profile_id == tenant_profile.id).all()
    )
    oldest = arrears["oldest"]
    since = None
    if oldest:
        y, m = (int(x) for x in oldest.split("-"))
        since = date(y, m, 1).strftime("%b %Y")
    return {
        "months_behind": arrears["count"],
        "rent_owed": arrears["total"],
        "unpaid_since": since,
        "utility_owed": round(utility_outstanding, 2),
        "total_owed": round(arrears["total"] + utility_outstanding, 2),
        "is_current": arrears["count"] == 0 and utility_outstanding <= 0,
    }
