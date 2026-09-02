"""Forward-looking figures for the admin dashboard.

The analytics already there report what has happened — revenue collected,
current occupancy, concerns resolved. None of it says what is about to,
so the dashboard reads as a record rather than something to plan from.

These functions answer the questions the owner actually acts on: which
contracts end soon and how much rent depends on them, what is already
overdue across every tenant, and what next month collects if nothing
changes.

Nothing here predicts. Every figure is arithmetic on contracts and
payments already recorded, so an administrator can trace any number back
to the rows it came from — a forecast nobody can check is worse than
none.
"""
from __future__ import annotations

import calendar
from datetime import date

from .billing_utils import (get_rent_arrears, utility_outstanding,
                            load_paid_months, load_latest_bills)
from sqlalchemy.orm import joinedload

from .extensions import db
from .models import TenantProfile, Unit, UtilityBill


def _month_label(d: date) -> str:
    return d.strftime("%B %Y")


def contract_expiry_outlook(months_ahead: int = 3, as_of: date | None = None) -> dict:
    """Contracts ending within the next `months_ahead` months, grouped by
    month, with the monthly rent that ends with each.

    Rent at risk is the tenant's own contract rent — what actually stops
    arriving if they do not renew — not the unit's asking price.
    """
    as_of = as_of or date.today()
    year, month = as_of.year, as_of.month
    index = year * 12 + (month - 1) + months_ahead
    horizon = date(index // 12, index % 12 + 1,
                   calendar.monthrange(index // 12, index % 12 + 1)[1])

    profiles = (
        db.session.query(TenantProfile)
        .options(joinedload(TenantProfile.user), joinedload(TenantProfile.unit))
        .filter(TenantProfile.is_active.is_(True),
                TenantProfile.contract_end.isnot(None),
                TenantProfile.contract_end >= as_of,
                TenantProfile.contract_end <= horizon)
        .order_by(TenantProfile.contract_end)
        .all()
    )

    buckets: dict[str, dict] = {}
    for p in profiles:
        key = f"{p.contract_end.year:04d}-{p.contract_end.month:02d}"
        bucket = buckets.setdefault(key, {
            "month": key,
            "label": _month_label(p.contract_end),
            "tenants": [],
            "rent_at_risk": 0.0,
        })
        bucket["tenants"].append({
            "name": p.user.full_name if p.user else "—",
            "unit": p.unit.unit_code if p.unit else "—",
            "ends_on": p.contract_end,
            "rent": p.contract_rent,
            "days_left": (p.contract_end - as_of).days,
        })
        bucket["rent_at_risk"] += p.contract_rent

    # Keep each month readable. The full list belongs on Tenant Monitoring,
    # which is filterable and paginated; the dashboard only has to say how
    # many and how much.
    SHOWN_PER_MONTH = 6
    months = sorted(buckets.values(), key=lambda b: b["month"])
    for bucket in months:
        bucket["total_tenants"] = len(bucket["tenants"])
        bucket["hidden"] = max(0, bucket["total_tenants"] - SHOWN_PER_MONTH)
        bucket["tenants"] = bucket["tenants"][:SHOWN_PER_MONTH]
    return {
        "months": months,
        "total_contracts": len(profiles),
        "total_rent_at_risk": round(sum(b["rent_at_risk"] for b in months), 2),
        "horizon_label": _month_label(horizon),
        "months_ahead": months_ahead,
    }


def collection_outlook(as_of: date | None = None) -> dict:
    """What next month bills if nothing changes, and what is already
    overdue right now across every active tenant.

    Expected rent counts only tenants whose contract still runs through
    next month — someone leaving before it does not bill. Utilities are
    excluded from the expectation because the electric reading is entered
    by the administrator each month and cannot be known in advance; the
    outstanding side does include them, since those amounts are real.
    """
    as_of = as_of or date.today()
    index = as_of.year * 12 + (as_of.month - 1) + 1
    nxt_year, nxt_month = index // 12, index % 12 + 1
    next_month_start = date(nxt_year, nxt_month, 1)
    next_month_end = date(nxt_year, nxt_month,
                          calendar.monthrange(nxt_year, nxt_month)[1])

    profiles = (db.session.query(TenantProfile)
                .options(joinedload(TenantProfile.user), joinedload(TenantProfile.unit))
                .filter(TenantProfile.is_active.is_(True)).all())

    # Load the payment and billing history for every tenant in two queries
    # rather than two per tenant. On a remote database the round trips, not
    # the arithmetic, are what make this page slow.
    ids = [p.id for p in profiles]
    paid_by_tenant = load_paid_months(ids)
    latest_bills = load_latest_bills(ids)

    expected_rent = 0.0
    billing_next_month = 0
    overdue_rent = 0.0
    overdue_utilities = 0.0
    tenants_behind = []

    for p in profiles:
        if not p.contract_end or p.contract_end >= next_month_start:
            expected_rent += p.contract_rent
            billing_next_month += 1

        arrears = get_rent_arrears(p, as_of, paid_by_tenant.get(p.id, set()))
        utilities = utility_outstanding(p, latest_bills.get(p.id))
        overdue_rent += arrears["total"]
        overdue_utilities += utilities

        # A tenant owing only electric or water is still behind. Counting
        # rent alone let the dashboard report money overdue "across 0
        # tenants", which reads as a fault in the figure.
        if arrears["count"] or utilities > 0:
            tenants_behind.append({
                "name": p.user.full_name if p.user else "—",
                "unit": p.unit.unit_code if p.unit else "—",
                "months": arrears["count"],
                "owed": round(arrears["total"] + utilities, 2),
                "profile_id": p.id,
            })

    tenants_behind.sort(key=lambda t: t["owed"], reverse=True)
    return {
        "next_month_label": _month_label(next_month_start),
        "next_month_end": next_month_end,
        "expected_rent": round(expected_rent, 2),
        "billing_next_month": billing_next_month,
        "overdue_rent": round(overdue_rent, 2),
        "overdue_utilities": round(overdue_utilities, 2),
        "overdue_total": round(overdue_rent + overdue_utilities, 2),
        "tenants_behind": tenants_behind[:5],
        "tenants_behind_count": len(tenants_behind),
    }


def occupancy_outlook(as_of: date | None = None) -> dict:
    """Occupancy now, and what it becomes if every contract ending in the
    next three months ends. The pessimistic case is the useful one — it is
    the number that tells the owner how many units to be marketing."""
    as_of = as_of or date.today()
    total = db.session.query(Unit).filter(Unit.is_archived.is_(False)).count()
    occupied = (db.session.query(TenantProfile)
                .filter(TenantProfile.is_active.is_(True)).count())
    expiring = contract_expiry_outlook(3, as_of)["total_contracts"]

    def pct(n):
        return round(n / total * 100, 1) if total else 0.0

    return {
        "total_units": total,
        "occupied_now": occupied,
        "rate_now": pct(occupied),
        "expiring": expiring,
        "occupied_if_none_renew": max(0, occupied - expiring),
        "rate_if_none_renew": pct(max(0, occupied - expiring)),
        "vacant_now": max(0, total - occupied),
    }
