#!/usr/bin/env python3
"""
Create inquiry system tables - FIXED VERSION
Matches the Inquiry and InquiryReply models
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Creating inquiry system tables (FIXED)...")
    print()
    
    # Drop old tables if they exist (to fix column mismatch)
    print("0. Dropping old tables if they exist...")
    try:
        db.session.execute(db.text("DROP TABLE IF EXISTS inquiry_replies"))
        db.session.execute(db.text("DROP TABLE IF EXISTS inquiries"))
        db.session.commit()
        print("   ✓ Old tables dropped")
    except Exception as e:
        print(f"   Note: {e}")
        db.session.rollback()
    
    # Create inquiries table (matching Inquiry model)
    sql_inquiries = """
    CREATE TABLE IF NOT EXISTS inquiries (
        id INT PRIMARY KEY AUTO_INCREMENT,
        full_name VARCHAR(120) NOT NULL,
        email VARCHAR(190) NOT NULL,
        phone VARCHAR(50),
        subject VARCHAR(200) NOT NULL,
        message TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_email (email),
        INDEX idx_status (status),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    # Create inquiry_replies table (matching InquiryReply model)
    sql_replies = """
    CREATE TABLE IF NOT EXISTS inquiry_replies (
        id INT PRIMARY KEY AUTO_INCREMENT,
        inquiry_id INT NOT NULL,
        admin_user_id INT NOT NULL,
        message TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE,
        FOREIGN KEY (admin_user_id) REFERENCES users(id),
        INDEX idx_inquiry_id (inquiry_id),
        INDEX idx_admin_user_id (admin_user_id)
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
        print("  - inquiries")
        print("    Columns: id, full_name, email, phone, subject, message, status, created_at, updated_at")
        print("  - inquiry_replies")
        print("    Columns: id, inquiry_id, admin_user_id, message, created_at")
        print()
        print("Status values: pending, responded, contacted")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        db.session.rollback()
