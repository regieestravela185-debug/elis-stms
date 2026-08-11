#!/usr/bin/env python3
"""
Migration: Add password reset fields to users table
Date: May 18, 2026
"""

import sys
from app import create_app
from app.extensions import db

def migrate():
    app = create_app()
    with app.app_context():
        print("🔧 Adding password reset fields to users table...")
        
        try:
            # Add reset_token column
            db.session.execute(db.text("""
                ALTER TABLE users 
                ADD COLUMN reset_token VARCHAR(100) NULL UNIQUE,
                ADD INDEX idx_reset_token (reset_token)
            """))
            print("✅ Added reset_token column with unique index")
            
            # Add reset_token_expires_at column
            db.session.execute(db.text("""
                ALTER TABLE users 
                ADD COLUMN reset_token_expires_at DATETIME NULL
            """))
            print("✅ Added reset_token_expires_at column")
            
            db.session.commit()
            print("✅ Migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    migrate()
