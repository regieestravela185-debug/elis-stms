"""How much security deposit a unit asks for, and how a partial payment is
applied against it.

Residential and commercial are priced differently. A studio asks for one
month's rent plus a flat one thousand; a commercial space asks for two
months' rent plus a flat ten thousand, because the fit-out a business
leaves behind costs more to restore. Both are collected together with the
first month's rent, so what an incoming tenant actually hands over is
rent + deposit.

Worked examples, from the property owner:

    residential, 6,000/month   deposit  7,000   move-in total 13,000
    commercial, 20,000/month   deposit 50,000   move-in total 70,000

A tenant may pay the move-in total in instalments. Whatever they pay is
credited to the SECURITY DEPOSIT first and the monthly rent is left whole,
because rent is income the property recognises for a specific month while
the deposit is money merely held — a half-paid month is a bookkeeping
problem, a half-paid deposit is only a smaller cushion.
"""

RESIDENTIAL_FLAT = 1000.00
COMMERCIAL_FLAT = 10000.00
COMMERCIAL_MONTHS = 2


def is_commercial(unit) -> bool:
    return "commercial" in ((getattr(unit, "type", None) or "").lower())


def security_deposit_for(unit) -> float:
    """The deposit a unit asks for, held and refundable minus damages."""
    monthly = float(getattr(unit, "price_monthly", 0) or 0)
    if is_commercial(unit):
        return monthly * COMMERCIAL_MONTHS + COMMERCIAL_FLAT
    return monthly + RESIDENTIAL_FLAT


def move_in_total_for(unit) -> float:
    """First month's rent plus the security deposit — what is due to move in."""
    return float(getattr(unit, "price_monthly", 0) or 0) + security_deposit_for(unit)


def deposit_breakdown(unit) -> dict:
    """The same figures, itemised for a receipt or a screen."""
    monthly = float(getattr(unit, "price_monthly", 0) or 0)
    commercial = is_commercial(unit)
    if commercial:
        parts = [(f"{COMMERCIAL_MONTHS} months' rent", monthly * COMMERCIAL_MONTHS),
                 ("Fixed commercial charge", COMMERCIAL_FLAT)]
    else:
        parts = [("One month's rent", monthly),
                 ("Fixed residential charge", RESIDENTIAL_FLAT)]
    deposit = security_deposit_for(unit)
    return {
        "commercial": commercial,
        "monthly": monthly,
        "parts": parts,
        "security_deposit": deposit,
        "first_month_rent": monthly,
        "move_in_total": monthly + deposit,
    }


def apply_partial(amount_paid, unit) -> dict:
    """Split what has been paid so far into deposit and rent.

    The deposit is filled first; only what is left over once the deposit is
    whole counts towards the first month's rent. A tenant who has paid half
    of a 70,000 move-in total has 35,000 of deposit on file and still owes
    the whole of the month's rent.
    """
    paid = max(0.0, float(amount_paid or 0))
    deposit_due = security_deposit_for(unit)
    rent_due = float(getattr(unit, "price_monthly", 0) or 0)

    deposit_paid = min(paid, deposit_due)
    rent_paid = min(paid - deposit_paid, rent_due)
    total_due = deposit_due + rent_due
    return {
        "paid": paid,
        "deposit_due": deposit_due,
        "deposit_paid": deposit_paid,
        "deposit_balance": deposit_due - deposit_paid,
        "rent_due": rent_due,
        "rent_paid": rent_paid,
        "rent_balance": rent_due - rent_paid,
        "total_due": total_due,
        "balance": total_due - paid,
        "settled": paid >= total_due - 0.005,
    }
