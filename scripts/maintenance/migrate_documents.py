#!/usr/bin/env python3
"""
Migration script to add new document features:
- uploaded_by field (track who uploaded)
- is_viewed field (has tenant viewed)
- viewed_at field (when tenant viewed)
- Create document_views table for tracking views/downloads
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Starting documents migration...")
    
    # Add new columns to documents table
    try:
        db.session.execute(db.text("""
            ALTER TABLE documents 
            ADD COLUMN IF NOT EXISTS uploaded_by INT NULL,
            ADD COLUMN IF NOT EXISTS is_viewed BOOLEAN DEFAULT FALSE NOT NULL,
            ADD COLUMN IF NOT EXISTS viewed_at DATETIME NULL
        """))
        print("✓ Added new columns to documents table")
    except Exception as e:
        print(f"⚠ Columns might already exist: {e}")
    
    try:
        db.session.execute(db.text("""
            ALTER TABLE documents 
            ADD INDEX IF NOT EXISTS idx_uploaded_by (uploaded_by)
        """))
        print("✓ Added index for uploaded_by")
    except Exception as e:
        print(f"⚠ Index might already exist: {e}")
    
    # Create document_views table
    try:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS document_views (
                id INT AUTO_INCREMENT PRIMARY KEY,
                document_id INT NOT NULL,
                user_id INT NOT NULL,
                viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                downloaded BOOLEAN DEFAULT FALSE NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_document_id (document_id),
                INDEX idx_user_id (user_id)
            )
        """))
        print("✓ Created document_views table")
    except Exception as e:
        print(f"⚠ document_views table might already exist: {e}")
    
    db.session.commit()
    print("\n✅ Migration completed successfully!")
    print("\nRun this script with: .venv/bin/python migrate_documents.py")
