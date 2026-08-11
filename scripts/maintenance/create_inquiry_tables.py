#!/usr/bin/env python3
"""
Create inquiry system tables
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Creating inquiry system tables...")
    print()
    
    # Create inquiries table
    sql_inquiries = """
    CREATE TABLE IF NOT EXISTS inquiries (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(120) NOT NULL,
        email VARCHAR(190) NOT NULL,
        phone VARCHAR(50),
        subject VARCHAR(200),
        message TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        responded_at DATETIME,
        responded_by INT,
        FOREIGN KEY (responded_by) REFERENCES users(id),
        INDEX idx_status (status),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    # Create inquiry_replies table
    sql_replies = """
    CREATE TABLE IF NOT EXISTS inquiry_replies (
        id INT PRIMARY KEY AUTO_INCREMENT,
        inquiry_id INT NOT NULL,
        admin_id INT NOT NULL,
        reply_message TEXT NOT NULL,
        sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE,
        FOREIGN KEY (admin_id) REFERENCES users(id),
        INDEX idx_inquiry_id (inquiry_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    try:
        print("1. Creating inquiries table...")
        db.session.execute(db.text(sql_inquiries))
        print("   ✓ inquiries table created")
        
        print("2. Creating inquiry_replies table...")
        db.session.execute(db.text(sql_replies))
        print("   ✓ inquiry_replies table created")
        
        db.session.commit()
        print()
        print("✅ All tables created successfully!")
        print()
        print("Tables created:")
        print("  - inquiries (stores inquiry submissions)")
        print("  - inquiry_replies (stores admin replies)")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        db.session.rollback()
