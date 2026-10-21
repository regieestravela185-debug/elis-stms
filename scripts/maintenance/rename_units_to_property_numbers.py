"""Rename every unit to the numbers the property itself uses.

The system was seeded with invented codes — B1-001, B2-A7, B5-D2 — while
the owner's own list names the units A through Z, 1 through 22, a P series
and an E series. Seventy-one names come off that list; the remaining
thirteen rooms are not on it and are numbered on from 22.

Series are kept together in a building rather than scattered, so a code
still tells you roughly where you are. The six commercial units named by
the owner go to Building 5, which already holds the commercial stock.

Nothing but the name changes. Tenants and reservations point at a unit by
its id, so they follow their unit automatically; payment references are
historical text and keep the code that was current when they were written,
which is also what keeps the hashed ledger intact.

    python rename_units.py            # dry run
    python rename_units.py --apply
"""
import sys

sys.path.insert(0, "/Users/regie-302004/Desktop/ElisSystem")

from app import create_app
from app.extensions import db
from app.models import Unit, Building, TenantProfile, Reservation

APPLY = "--apply" in sys.argv

LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVW") + ["Y", "Z"]
NUMBERS = ["1", "2", "3", "5", "6", "7", "8", "9", "10", "11", "12", "12A",
           "12B", "15", "16", "17", "18", "19", "20", "21", "22"]
P_SERIES = ["P1", "P2", "P3", "P3A", "P5", "P6", "P7", "P8", "P9", "P10",
            "P11", "P12"]
E_SERIES = ["E1", "E2", "E3", "E5A", "E5B", "E5C", "E7", "E8", "E9", "E10",
            "E11", "E12", "E12A"]
COMMERCIAL = {"E1", "E2", "E3", "E5A", "E5B", "P1"}
EXTRA = [str(n) for n in range(23, 36)]        # the thirteen not on the list

PLAN = {
    "B1": EXTRA + LETTERS[:9],                           # 13 + A..I  = 22
    "B2": NUMBERS,                                       # 1..22      = 21
    "B3": LETTERS[9:] + ["P2", "P3"],                    # J..Z + P2,P3 = 18
    "B4": ["P3A"] + P_SERIES[4:] + ["E5C"] + E_SERIES[6:],   # 17
    "B5": ["E1", "E2", "E3", "E5A", "E5B", "P1"],        # commercial = 6
}


def main():
    app = create_app()
    with app.app_context():
        db.session.commit = db.session.flush if not APPLY else db.session.commit

        every = [n for names in PLAN.values() for n in names]
        assert len(every) == len(set(every)) == 84, f"{len(every)} names, {len(set(every))} unique"

        changes, problems = [], []
        for code, names in PLAN.items():
            b = db.session.query(Building).filter_by(code=code).first()
            if not b:
                problems.append(f"walang building {code}")
                continue
            units = (db.session.query(Unit)
                     .filter_by(building_id=b.id)
                     .order_by(Unit.floor.asc(), Unit.id.asc()).all())
            if len(units) != len(names):
                problems.append(f"{code}: {len(units)} unit pero {len(names)} pangalan")
                continue
            for u, name in zip(units, names):
                kind = "commercial" if name in COMMERCIAL else "residential"
                changes.append((u.id, u.unit_code, name, u.type, kind,
                                b.code, u.floor))

        if problems:
            print("=== HINDI MATULOY ===")
            for p in problems:
                print(f"  {p}")
            raise SystemExit(1)

        tenants = {t.unit_id: t for t in db.session.query(TenantProfile)
                   .filter(TenantProfile.is_active.is_(True)).all()}
        resv = {}
        for r in db.session.query(Reservation).all():
            resv.setdefault(r.unit_id, 0)
            resv[r.unit_id] += 1

        print("=== BAGONG PANGALAN ===")
        last = None
        for uid, old, new, oldt, newt, bcode, floor in changes:
            if bcode != last:
                print(f"\n  --- {bcode} ---")
                last = bcode
            flags = []
            if oldt != newt:
                flags.append(f"{oldt} -> {newt.upper()}")
            if uid in tenants:
                flags.append(f"MAY TENANT: {tenants[uid].user.full_name}")
            if resv.get(uid):
                flags.append(f"{resv[uid]} reservation")
            print(f"    p{floor}  {old:8} -> {new:5} {'  | ' + ', '.join(flags) if flags else ''}")

        print(f"\n  {len(changes)} unit")
        print(f"  commercial: {sum(1 for c in changes if c[4]=='commercial')}")
        print(f"  may tenant: {sum(1 for c in changes if c[0] in tenants)}")

        if not APPLY:
            print("\nDRY RUN — walang nasulat.")
            return

        for uid, old, new, oldt, newt, bcode, floor in changes:
            u = db.session.get(Unit, uid)
            u.unit_code = new
            u.unit_number = new
            u.type = newt
        db.session.commit()
        print("\nNa-save.")


main()
