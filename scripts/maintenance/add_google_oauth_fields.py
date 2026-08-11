#!/usr/bin/env python3
"""
Migration: Add Google OAuth fields to users table
Phase 2: Google OAuth Integration
Date: May 18, 2026
"""

import sys
from sqlalchemy import text
from app import create_app, db

def migrate():
    app = create_app()
    with app.app_context():
        try:
            # Add google_id column
            db.session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN google_id VARCHAR(255) NULL UNIQUE
            """))
            print("✅ Added google_id column with unique constraint")
            
            # Add index for google_id
            db.session.execute(text("""
                ALTER TABLE users 
                ADD INDEX idx_google_id (google_id)
            """))
            print("✅ Added index for google_id")
            
            # Add oauth_provider column
            db.session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN oauth_provider VARCHAR(50) NOT NULL DEFAULT 'email'
            """))
            print("✅ Added oauth_provider column (default: 'email')")
            
            # Add profile_picture column
            db.session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN profile_picture VARCHAR(500) NULL
            """))
            print("✅ Added profile_picture column")
            
            db.session.commit()
            print("\n🎉 Migration completed successfully!")
            print("\nGoogle OAuth fields added:")
            print("  - google_id (VARCHAR 255, UNIQUE, INDEXED)")
            print("  - oauth_provider (VARCHAR 50, DEFAULT 'email')")
            print("  - profile_picture (VARCHAR 500, NULL)")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Migration failed: {e}")
            print("\nNote: If columns already exist, this is expected.")
            sys.exit(1)

if __name__ == "__main__":
    migrate()
