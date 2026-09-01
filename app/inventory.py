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

# Conditions that mean the item needs attention before a new tenant moves in.
CONDITION_NEEDS_ATTENTION = ("damaged", "missing")


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
    """Counts an administrator needs at a glance, and the short list a
    prospective tenant sees on the homepage."""
    recorded = [i for i in items if (i.quantity or 0) > 0]
    attention = [i for i in recorded if i.condition in CONDITION_NEEDS_ATTENTION]
    return {
        "total_items": len(recorded),
        "total_units": sum(i.quantity or 0 for i in recorded),
        "needs_attention": attention,
        "attention_count": len(attention),
        "is_encoded": bool(recorded),
        "highlights": recorded[:6],
    }
