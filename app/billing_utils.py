from __future__ import annotations

import calendar
from datetime import date

from .extensions import db
from .models import TenantProfile, UtilityBill

# Distinguishes "nothing passed" from "passed None" — a tenant with no
# bill at all is a real answer, not a missing argument.
_UNSET = object()
from .ai_utils import compute_water_bill


def first_utility_month(tenant_profile: TenantProfile) -> str | None:
    """The first month a tenant is billed for electric and water.

    Utilities start the month AFTER move-in: a tenant who moves in on
    26 August has no utility bill for August and is first billed in
    September. Their first month's consumption is not metered separately
    from the outgoing tenant's, so there is nothing to charge them for.
    """
    start = tenant_profile.contract_start
    if not start:
        return None
    return _month_add(f"{start.year:04d}-{start.month:02d}", 1)


def get_or_create_utility_bill(tenant_profile: TenantProfile,
                               billing_month: str) -> UtilityBill | None:
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

    Returns None for any month before the tenant's first billable one —
    utilities begin the month after move-in (see first_utility_month), so
    the month they moved in has no bill at all. Callers must skip a None
    rather than render a row for it.

    Does not commit — the caller controls the transaction (the admin
    bulk-input page commits once after creating a whole page of rows;
    the reminder job commits once after its whole pass).
    """
    first = first_utility_month(tenant_profile)
    if not first or billing_month < first:
        return None

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

    # The most recent EARLIER bill, not strictly last month's. Viewing a
    # month on the admin billing page creates it, so an administrator who
    # skips ahead — October, then December — leaves a gap. Asking only for
    # the month immediately before would find nothing there and silently
    # drop the balance October was still owed.
    prior_bill = (
        db.session.query(UtilityBill)
        .filter(
            UtilityBill.tenant_profile_id == tenant_profile.id,
            UtilityBill.billing_month < billing_month,
        )
        .order_by(UtilityBill.billing_month.desc())
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


def billing_month_for(tenant_profile: TenantProfile, when: date) -> str | None:
    """Which billing cycle a payment made on `when` settles.

    Cycles run from the contract's anniversary day, so a payment belongs
    to the most recent cycle whose due date has already arrived — a
    tenant paying on 3 September for a 26th-of-the-month contract is
    settling the cycle that began 26 August, not the one starting 26
    September.

    Returns None for a payment dated before the contract began, since
    there is no cycle for it to settle.
    """
    start = tenant_profile.contract_start
    if not start or when < start:
        return None
    year, month = when.year, when.month
    due_day = min(start.day, calendar.monthrange(year, month)[1])
    if when.day < due_day:
        # Before this month's due date, so it settles the previous cycle.
        return _month_add(f"{year:04d}-{month:02d}", -1)
    return f"{year:04d}-{month:02d}"


def load_paid_months(profile_ids) -> dict:
    """Every tenant's settled rent months, in ONE query.

    get_rent_arrears asks this per tenant, which is fine for one row but
    becomes a query per tenant on any page that covers them all. Callers
    working with a whole set of tenants load it once and pass it in.
    """
    from .models import Payment, PAYMENT_STATUSES_NOT_COUNTED

    ids = list(profile_ids)
    if not ids:
        return {}
    out: dict = {pid: set() for pid in ids}
    for pid, month in (db.session.query(Payment.tenant_profile_id,
                                        Payment.payment_month)
                       .filter(Payment.tenant_profile_id.in_(ids),
                               Payment.payment_month.isnot(None),
                               Payment.is_deposit.is_(False),
                               Payment.payment_status.notin_(PAYMENT_STATUSES_NOT_COUNTED))
                       .all()):
        out[pid].add(month)
    return out


def load_latest_bills(profile_ids) -> dict:
    """Each tenant's newest utility bill, in ONE query.

    The newest bill is the running total — see utility_outstanding — so
    this is all a caller needs to know what is still owed.
    """
    from .models import UtilityBill

    ids = list(profile_ids)
    if not ids:
        return {}
    latest: dict = {}
    for b in (db.session.query(UtilityBill)
              .filter(UtilityBill.tenant_profile_id.in_(ids))
              .order_by(UtilityBill.tenant_profile_id,
                        UtilityBill.billing_month)
              .all()):
        latest[b.tenant_profile_id] = b  # ordered ascending, so last wins
    return latest


def get_unpaid_rent_months(tenant_profile: TenantProfile, as_of: date | None = None,
                           paid_months=None):
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

    if paid_months is None:
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


def get_rent_arrears(tenant_profile: TenantProfile, as_of: date | None = None,
                     paid_months=None) -> dict:
    """Summary of what the tenant still owes in rent.

    Returns months (oldest first), their count, the monthly rate, and the
    total. Unpaid months are valued at the tenant's own contract rent, so
    raising the unit's asking price for future tenants never revalues what
    someone already owes.
    """
    months = get_unpaid_rent_months(tenant_profile, as_of, paid_months)
    rate = tenant_profile.contract_rent
    return {
        "months": months,
        "count": len(months),
        "monthly_rate": rate,
        "total": round(rate * len(months), 2),
        "oldest": months[0] if months else None,
    }


def next_rent_due(tenant_profile: TenantProfile, as_of: date | None = None):
    """The rent month this tenant owes next — {month, label, due_date, state}.

    "Next" means the earliest month they have not settled, which is not the
    same as the next date on the calendar: a tenant who has paid this month
    owes the month after, and one who missed a month owes that one, however
    long ago it fell. Computing it from the calendar alone told a tenant who
    had just paid that rent was due in eleven days.

    `state` is "unpaid" when that month's due date has already passed and
    "upcoming" when it has not. Returns None for a tenant with no contract
    start, or one whose contract has ended before the month they owe.
    """
    as_of = as_of or date.today()
    start = tenant_profile.contract_start
    if not start:
        return None

    timeline = get_payment_timeline(tenant_profile, as_of)
    row = next((r for r in reversed(timeline) if r["rent_state"] != "paid"), None)
    if row is not None:
        return {"month": row["month"], "label": row["label"],
                "due_date": row["due_date"], "state": row["rent_state"]}

    # Every month up to the current cycle is settled, so what they owe next
    # is the cycle after the last one the timeline covers.
    month_str = timeline[0]["month"] if timeline else f"{as_of.year:04d}-{as_of.month:02d}"
    year, month = (int(x) for x in _month_add(month_str, 1).split("-"))
    due = date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
    if tenant_profile.contract_end and due > tenant_profile.contract_end:
        return None
    return {"month": f"{year:04d}-{month:02d}",
            "label": due.strftime("%B %Y"), "due_date": due, "state": "upcoming"}


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


def utility_outstanding(tenant_profile: TenantProfile, latest=_UNSET) -> float:
    """What a tenant still owes on electric and water, in total.

    This is the LATEST bill's outstanding, not the sum across bills. Each
    month's bill carries forward whatever the month before left unpaid, so
    the newest one is already the running total — adding the older ones to
    it counts the same peso once for every month it has rolled through.
    """
    from .models import UtilityBill

    if latest is _UNSET:
        latest = (db.session.query(UtilityBill)
                  .filter(UtilityBill.tenant_profile_id == tenant_profile.id)
                  .order_by(UtilityBill.billing_month.desc())
                  .first())
    return round(latest.total_outstanding, 2) if latest else 0.0


def payment_standing(tenant_profile: TenantProfile, as_of: date | None = None,
                     paid_months=None, latest_bill=_UNSET) -> dict:
    """One-line standing for a monitoring row: how far behind, since when,
    and whether utilities are outstanding too."""
    from .models import UtilityBill

    arrears = get_rent_arrears(tenant_profile, as_of, paid_months)
    owed_on_utilities = utility_outstanding(tenant_profile, latest_bill)
    oldest = arrears["oldest"]
    since = None
    if oldest:
        y, m = (int(x) for x in oldest.split("-"))
        since = date(y, m, 1).strftime("%b %Y")
    return {
        "months_behind": arrears["count"],
        "rent_owed": arrears["total"],
        "unpaid_since": since,
        "utility_owed": owed_on_utilities,
        "total_owed": round(arrears["total"] + owed_on_utilities, 2),
        "is_current": arrears["count"] == 0 and owed_on_utilities <= 0,
    }


def final_settlement(tenant_profile: TenantProfile, as_of: date | None = None) -> dict:
    """Everything owed when a tenant leaves, set against their deposit.

    Three charges are totalled: rent months never paid, electricity and
    water left outstanding, and fixtures whose recorded condition costs
    something. The administrator used to type each of these in by hand as a
    free-text deduction; here they are read from the records that already
    hold them, so the figures can be checked rather than taken on trust.

    Fixtures are priced by what their condition actually calls for, not by
    one blanket rule: an item worn to `fair` is repaired, so it is charged
    the repair cost; one `damaged` is paid for and one `missing` bought
    again, both at the replacement cost. See CONDITION_OUTCOMES in
    app/inventory.py.

    The result is deliberately NOT applied to anything. It is a statement
    the administrator reviews, because two outcomes are possible and only
    they can know which happened: the charges come out of the deposit and
    the remainder is returned, or the tenant pays the charges separately
    and takes the deposit back in full.

    Fixtures with no cost recorded for what their condition calls for are
    still listed, but contribute nothing to the total — an unpriced item
    should be visible and questioned, not silently charged at zero or
    guessed at.
    """
    from .models import Reservation, UnitInventoryItem
    from .inventory import price_item

    as_of = as_of or date.today()
    arrears = get_rent_arrears(tenant_profile, as_of)

    from .models import UtilityBill
    # The newest bill already carries every earlier unpaid month, so it is
    # the running total — summing the bills would charge the same balance
    # once for each month it rolled through.
    latest_bill = (db.session.query(UtilityBill)
                   .filter(UtilityBill.tenant_profile_id == tenant_profile.id)
                   .order_by(UtilityBill.billing_month.desc()).first())
    electric_owed = latest_bill.electric_outstanding if latest_bill else 0.0
    water_owed = latest_bill.water_outstanding if latest_bill else 0.0

    damaged, damage_owed, unpriced = [], 0.0, 0
    repair_owed, replace_owed = 0.0, 0.0
    for row in (db.session.query(UnitInventoryItem)
                .filter(UnitInventoryItem.unit_id == tenant_profile.unit_id)
                .order_by(UnitInventoryItem.sort_order).all()):
        line = price_item(row)
        if not line["chargeable"]:
            continue
        damage_owed += line["line_total"]
        if line["basis"] == "repair":
            repair_owed += line["line_total"]
        else:
            replace_owed += line["line_total"]
        if not line["is_priced"]:
            unpriced += 1
        damaged.append({
            "label": line["label"], "condition": line["condition_label"],
            "condition_key": line["condition"], "outcome": line["outcome"],
            "basis": line["basis"], "quantity": line["quantity"],
            "unit_cost": line["unit_cost"], "line_total": line["line_total"],
            "notes": line["notes"], "is_priced": line["is_priced"],
        })

    # The deposit lives on the tenant's reservation, which is where it was
    # taken. Fall back to zero rather than guessing an amount.
    reservation = (db.session.query(Reservation)
                   .filter(Reservation.unit_id == tenant_profile.unit_id,
                           Reservation.user_id == tenant_profile.user_id)
                   .order_by(Reservation.id.desc()).first())
    deposit = float(reservation.deposit_amount or 0) if reservation else 0.0

    total_owed = round(arrears["total"] + electric_owed + water_owed + damage_owed, 2)
    releasable = tenant_profile.deposit_releasable_on

    return {
        "rent": {"months": arrears["months"], "count": arrears["count"],
                 "rate": arrears["monthly_rate"], "total": arrears["total"]},
        "electric_owed": round(electric_owed, 2),
        "water_owed": round(water_owed, 2),
        "damaged": damaged,
        "damage_owed": round(damage_owed, 2),
        # Split, so a settlement never reads a repair as a replacement.
        "repair_owed": round(repair_owed, 2),
        "replace_owed": round(replace_owed, 2),
        "unpriced_damage_count": unpriced,
        "total_owed": total_owed,
        "deposit": deposit,
        "reservation": reservation,
        # If the charges come out of the deposit:
        "refund_after_deduction": round(max(0.0, deposit - total_owed), 2),
        "shortfall": round(max(0.0, total_owed - deposit), 2),
        # If the tenant settles separately, the deposit returns untouched.
        "refund_if_tenant_pays": deposit,
        "moved_out_on": tenant_profile.moved_out_on,
        "releasable_on": releasable,
        "is_releasable": bool(releasable and releasable <= as_of),
        "days_until_releasable": (releasable - as_of).days if releasable else None,
    }
