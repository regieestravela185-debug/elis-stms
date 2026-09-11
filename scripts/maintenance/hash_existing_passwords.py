"""Replace every plain-text password in users.password_hash with a hash.

Accounts created before hashing was introduced hold the password itself in
that column — readable by anyone with database access. This rewrites each
one as a Werkzeug scrypt hash.

The change is one-way: the passwords themselves are gone afterwards, which
is the point. Nobody has to reset anything — verify_password still accepts
both shapes, and a login on an account this script has not reached upgrades
it on the spot.

    python scripts/maintenance/hash_existing_passwords.py --dry-run
    python scripts/maintenance/hash_existing_passwords.py
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app, db                     # noqa: E402
from app.models import User                        # noqa: E402
from app.security import hash_password, is_legacy_password  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change and write nothing")
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        users = User.query.order_by(User.id).all()
        legacy = [u for u in users if is_legacy_password(u.password_hash)]
        hashed = len(users) - len(legacy)

        print(f"{len(users)} account: {hashed} naka-hash na, {len(legacy)} plain text")
        if not legacy:
            print("wala nang aayusin.")
            return

        for u in legacy:
            print(f"  {u.id:>4}  {u.email:<40} {u.role.value}")

        if args.dry_run:
            print("\n--dry-run: walang isinulat.")
            return

        for u in legacy:
            u.password_hash = hash_password(u.password_hash)
        db.session.commit()

        remaining = [u for u in User.query.all() if is_legacy_password(u.password_hash)]
        print(f"\n{len(legacy)} account na-hash. Natitirang plain text: {len(remaining)}")


if __name__ == "__main__":
    main()
