"""Add reservations.id_review_reason.

Records why a declared ID type or number could not be confirmed against the
uploaded photo. Existing rows get NULL, which reads as "not recorded" —
they predate the check.

    python scripts/maintenance/add_id_review_reason.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from sqlalchemy import text
from app import create_app, db

SQL = """
ALTER TABLE reservations
ADD COLUMN IF NOT EXISTS id_review_reason VARCHAR(255) NULL;
"""

app = create_app()
with app.app_context():
    db.session.execute(text(SQL))
    db.session.commit()
    n = db.session.execute(text(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name='reservations' AND column_name='id_review_reason'"
    )).scalar()
    print("id_review_reason present:", bool(n))
