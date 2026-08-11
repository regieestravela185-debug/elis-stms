#!/usr/bin/env python
"""Add admin_response fields to feedbacks table"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Adding admin_response fields to feedbacks table...")
    
    # Add columns using raw SQL
    try:
        db.session.execute(db.text("""
            ALTER TABLE feedbacks 
            ADD COLUMN admin_response TEXT NULL,
            ADD COLUMN admin_response_at DATETIME NULL,
            ADD COLUMN admin_response_by INT NULL
        """))
        db.session.commit()
        print("✅ Successfully added admin_response, admin_response_at, and admin_response_by columns!")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("✓ Columns already exist, skipping...")
        else:
            print(f"❌ Error: {e}")
            db.session.rollback()
