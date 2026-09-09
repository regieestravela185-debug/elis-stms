"""The fixtures and furnishings that come with a residential unit.

This list is the same one printed in the Kasunduan's "MGA GAMIT NA NASA
LOOB NG UNIT" table, which the parties used to fill in by hand at
signing. Holding it as data instead means the same figures feed three
places that previously had no connection to each other: the Kasunduan is
generated already filled in, prospective tenants can see what a unit
comes with before they reserve, and the condition recorded at move-in is
there to compare against at move-out.

Labels are stored on the row rather than referenced by key, so a unit
keeps the wording it was inventoried under even if this list is later
revised.
"""
from __future__ import annotations

# Order matters — it is the order the Kasunduan prints and the admin
# encodes, grouped so related fixtures stay together.
STANDARD_UNIT_INVENTORY = [
    "Floor Tiles",
    "Double Deck Beds",
    "Mattress",
    "Doors — Front",
    "Doors — Back",
    "Doors — CR/Bathroom",
    "CR/Bathroom Fixtures — Faucets",
    "CR/Bathroom Fixtures — Shower",
    "CR/Bathroom Fixtures — Bidet",
    "CR/Bathroom Fixtures — Toilet Bowl",
    "CR/Bathroom Fixtures — Sink",
    "CR/Bathroom Fixtures — Pail/Dipper",
    "Bulbs",
    "Door Locks — Front",
    "Door Locks — Back",
    "Door Locks — CR/Bathroom",
    "Keys & Key Holder",
]

# Stored value -> what the administrator and tenant read. Bilingual because
# the Kasunduan itself is in Filipino and tenants sign that version.
INVENTORY_CONDITIONS = [
    ("new", "Bago / New"),
    ("good", "Maayos / Good"),
    ("fair", "Katamtaman / Fair"),
    ("damaged", "May sira / Damaged"),
    ("missing", "Wala / Missing"),
]

CONDITION_LABELS = dict(INVENTORY_CONDITIONS)
CONDITION_KEYS = [k for k, _ in INVENTORY_CONDITIONS]

# What each condition actually means for the tenant, and which recorded
# price it is charged against.
#
# The three that cost something are deliberately not the same outcome. An
# item worn to "fair" is not written off — it gets repaired, so it is
# charged the repair cost, not the price of a new one. Something with real
# damage is paid for, and something gone has to be bought again; both of
# those carry the item's full value. Collapsing them, as this used to,
# charged a scuffed door the price of a new door.
#
#   basis   - which cost column prices one of these ("repair" | "replacement")
#   outcome - what happens, in the words the Kasunduan uses
CONDITION_OUTCOMES = {
    "new":     {"basis": None,          "outcome": "Walang bayad / No charge",
                "detail": "Brand new — nothing owed.", "tone": "ok"},
    "good":    {"basis": None,          "outcome": "Walang bayad / No charge",
                "detail": "In order — nothing owed.", "tone": "ok"},
    "fair":    {"basis": "repair",      "outcome": "Ipapaayos lang / Repair only",
                "detail": "Worn but serviceable. It is repaired, not replaced, "
                          "so only the repair cost is charged.", "tone": "watch"},
    "damaged": {"basis": "replacement", "outcome": "Babayaran / Charged to tenant",
                "detail": "Damaged beyond a repair. The tenant pays its value.",
                "tone": "charge"},
    "missing": {"basis": "replacement", "outcome": "Papalitan / To be replaced",
                "detail": "Gone. It has to be bought again, at its "
                          "replacement price.", "tone": "charge"},
}

# Conditions that mean the item needs attention before a new tenant moves
# in — fair included, because "repair only" is still a repair someone has
# to carry out.
CONDITION_NEEDS_ATTENTION = ("fair", "damaged", "missing")

# The conditions that put money on the final settlement.
CONDITION_CHARGEABLE = ("fair", "damaged", "missing")

# Conditions where the item is beyond repair, kept separate from `fair` so
# the two are never lumped into one "damage" figure again.
CONDITION_FULL_VALUE = ("damaged", "missing")


def condition_outcome(condition: str) -> dict:
    """What a recorded condition means, and how it is priced."""
    return CONDITION_OUTCOMES.get(condition) or {
        "basis": None, "outcome": CONDITION_LABELS.get(condition, condition or "—"),
        "detail": "", "tone": "ok",
    }


def price_item(item) -> dict:
    """Price one inventory row: quantity times whichever cost its condition
    calls for.

    Returns the line even when it costs nothing, so a caller can show a
    complete table and a total that adds up. `is_priced` is False when the
    condition does charge but no amount was ever recorded for it — that
    line is reported and left at zero rather than guessed at.
    """
    spec = condition_outcome(item.condition)
    basis = spec["basis"]
    quantity = int(item.quantity or 0)

    if basis == "repair":
        unit_cost = float(item.repair_cost or 0)
    elif basis == "replacement":
        unit_cost = float(item.replacement_cost or 0)
    else:
        unit_cost = 0.0

    return {
        "label": item.label,
        "condition": item.condition,
        "condition_label": CONDITION_LABELS.get(item.condition, item.condition),
        "outcome": spec["outcome"],
        "detail": spec["detail"],
        "tone": spec["tone"],
        "basis": basis,
        "quantity": quantity,
        "unit_cost": unit_cost,
        "line_total": round(unit_cost * quantity, 2),
        "chargeable": basis is not None and quantity > 0,
        "is_priced": basis is None or unit_cost > 0,
        "notes": item.notes,
    }


def ensure_unit_inventory(unit, commit: bool = False):
    """Give a unit the standard inventory rows it is missing, and return
    all of its rows in display order.

    Idempotent: a row already present keeps its recorded quantity and
    condition. Rows the administrator added by hand are preserved and sort
    after the standard ones. Does not commit unless asked, so a caller
    filling several units pays for one transaction.
    """
    from .extensions import db
    from .models import UnitInventoryItem

    existing = (
        db.session.query(UnitInventoryItem)
        .filter(UnitInventoryItem.unit_id == unit.id)
        .all()
    )
    have = {row.label for row in existing}

    for order, label in enumerate(STANDARD_UNIT_INVENTORY):
        if label not in have:
            db.session.add(UnitInventoryItem(
                unit_id=unit.id, label=label, sort_order=order,
                quantity=0, condition="good",
            ))
    if not have or len(have) < len(STANDARD_UNIT_INVENTORY):
        db.session.flush()
    if commit:
        db.session.commit()

    return (
        db.session.query(UnitInventoryItem)
        .filter(UnitInventoryItem.unit_id == unit.id)
        .order_by(UnitInventoryItem.sort_order, UnitInventoryItem.id)
        .all()
    )


def inventory_summary(items) -> dict:
    """Counts and money an administrator needs at a glance, and the short
    list a prospective tenant sees on the homepage.

    The money side answers the question the per-row prices exist for: what
    would this unit's inventory cost to put right today, split so repairs
    are not read as replacements.
    """
    recorded = [i for i in items if (i.quantity or 0) > 0]
    attention = [i for i in recorded if i.condition in CONDITION_NEEDS_ATTENTION]

    lines = [price_item(i) for i in recorded]
    repair_lines = [l for l in lines if l["basis"] == "repair"]
    replace_lines = [l for l in lines if l["basis"] == "replacement"]
    unpriced = [l for l in lines if l["chargeable"] and not l["is_priced"]]

    repair_total = round(sum(l["line_total"] for l in repair_lines), 2)
    replace_total = round(sum(l["line_total"] for l in replace_lines), 2)

    # What the whole inventory is worth at replacement price, whatever
    # condition it is in — the figure to compare a deposit against.
    inventory_value = round(
        sum(float(i.replacement_cost or 0) * (i.quantity or 0) for i in recorded), 2)

    return {
        "total_items": len(recorded),
        "total_units": sum(i.quantity or 0 for i in recorded),
        "needs_attention": attention,
        "attention_count": len(attention),
        "is_encoded": bool(recorded),
        "highlights": recorded[:6],

        "lines": lines,
        "repair_lines": repair_lines,
        "replace_lines": replace_lines,
        "repair_total": repair_total,
        "replace_total": replace_total,
        "charge_total": round(repair_total + replace_total, 2),
        "inventory_value": inventory_value,
        "unpriced": unpriced,
        "unpriced_count": len(unpriced),
        "priced_count": sum(1 for i in recorded
                            if float(i.replacement_cost or 0) > 0
                            or float(i.repair_cost or 0) > 0),
    }
