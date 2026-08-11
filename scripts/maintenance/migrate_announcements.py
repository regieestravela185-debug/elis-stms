#!/usr/bin/env python3
"""
Migration script to add new announcement features:
- is_pinned field
- target_audience field
- expires_at field
- Create announcement_reads table for tracking read status
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Starting announcements migration...")
    
    # Add new columns to announcements table
    try:
        db.session.execute(db.text("""
            ALTER TABLE announcements 
            ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE NOT NULL
        """))
        print("✓ Added is_pinned column")
    except Exception as e:
        print(f"⚠ is_pinned column might already exist: {e}")
    
    try:
        db.session.execute(db.text("""
            ALTER TABLE announcements 
            ADD COLUMN IF NOT EXISTS target_audience VARCHAR(20) DEFAULT 'all' NOT NULL
        """))
        print("✓ Added target_audience column")
    except Exception as e:
        print(f"⚠ target_audience column might already exist: {e}")
    
    try:
        db.session.execute(db.text("""
            ALTER TABLE announcements 
            ADD COLUMN IF NOT EXISTS expires_at DATETIME NULL
        """))
        print("✓ Added expires_at column")
    except Exception as e:
        print(f"⚠ expires_at column might already exist: {e}")
    
    # Create announcement_reads table
    try:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS announcement_reads (
                id INT AUTO_INCREMENT PRIMARY KEY,
                announcement_id INT NOT NULL,
                user_id INT NOT NULL,
                read_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (announcement_id) REFERENCES announcements(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_announcement_id (announcement_id),
                INDEX idx_user_id (user_id),
                UNIQUE KEY unique_read (announcement_id, user_id)
            )
        """))
        print("✓ Created announcement_reads table")
    except Exception as e:
        print(f"⚠ announcement_reads table might already exist: {e}")
    
    db.session.commit()
    print("\n✅ Migration completed successfully!")
    print("\nRun this script with: .venv/bin/python migrate_announcements.py")
