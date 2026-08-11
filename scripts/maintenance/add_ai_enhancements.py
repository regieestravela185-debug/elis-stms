#!/usr/bin/env python3
"""
Database Migration Script for AI Enhancements
Adds fields for:
1. AI-Assisted Identity Verification
2. NLP-Based Smart Chat Assistant
3. Predictive Analytics for Late Payments
4. Smart Notification System
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.extensions import db
from sqlalchemy import text
from app import create_app


def migrate_identity_verification():
    """Add identity verification fields to Reservation model"""
    print("Migrating identity verification fields...")
    
    try:
        # Add selfie_image field to reservations table
        db.session.execute(text("""
            ALTER TABLE reservations 
            ADD COLUMN selfie_image VARCHAR(255) NULL 
            COMMENT 'Path to uploaded selfie image for facial recognition'
        """))
        print("✓ Added selfie_image to reservations")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("  - selfie_image already exists")
        else:
            print(f"✗ Error adding selfie_image: {e}")
    
    try:
        # Add face_match_score field to reservations table
        db.session.execute(text("""
            ALTER TABLE reservations 
            ADD COLUMN face_match_score DECIMAL(5,4) NULL 
            COMMENT 'Face matching score between ID and selfie (0-1)'
        """))
        print("✓ Added face_match_score to reservations")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("  - face_match_score already exists")
        else:
            print(f"✗ Error adding face_match_score: {e}")
    
    try:
        # Add verification_status field to reservations table
        db.session.execute(text("""
            ALTER TABLE reservations 
            ADD COLUMN verification_status ENUM('pending', 'verified', 'failed', 'manual_review') 
            DEFAULT 'pending' 
            COMMENT 'AI verification status'
        """))
        print("✓ Added verification_status to reservations")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("  - verification_status already exists")
        else:
            print(f"✗ Error adding verification_status: {e}")
    
    try:
        # Add fake_id_flag field to reservations table
        db.session.execute(text("""
            ALTER TABLE reservations 
            ADD COLUMN fake_id_flag BOOLEAN DEFAULT FALSE 
            COMMENT 'Flag for potential fake ID detection'
        """))
        print("✓ Added fake_id_flag to reservations")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("  - fake_id_flag already exists")
        else:
            print(f"✗ Error adding fake_id_flag: {e}")


def migrate_nlp_chat():
    """Add NLP chat fields"""
    print("\nMigrating NLP chat fields...")
    
    # Create chat_logs table
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                user_role ENUM('admin', 'tenant', 'customer') NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                detected_intent VARCHAR(100) NULL,
                chatbot_confidence_score DECIMAL(5,4) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) COMMENT='NLP chat conversation logs'
        """))
        print("✓ Created chat_logs table")
    except Exception as e:
        if "already exists" in str(e):
            print("  - chat_logs table already exists")
        else:
            print(f"✗ Error creating chat_logs table: {e}")


def migrate_predictive_analytics():
    """Add predictive analytics fields to tenant_profiles"""
    print("\nMigrating predictive analytics fields...")
    
    try:
        # Add payment_risk_level field to tenant_profiles table
        db.session.execute(text("""
            ALTER TABLE tenant_profiles 
            ADD COLUMN payment_risk_level ENUM('low', 'medium', 'high') 
            DEFAULT 'low' 
            COMMENT 'Predicted payment risk level'
        """))
        print("✓ Added payment_risk_level to tenant_profiles")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("  - payment_risk_level already exists")
        else:
            print(f"✗ Error adding payment_risk_level: {e}")
    
    try:
        # Add prediction_score field to tenant_profiles table
        db.session.execute(text("""
            ALTER TABLE tenant_profiles 
            ADD COLUMN prediction_score DECIMAL(5,4) NULL 
            COMMENT 'AI prediction score for late payment risk (0-1)'
        """))
        print("✓ Added prediction_score to tenant_profiles")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("  - prediction_score already exists")
        else:
            print(f"✗ Error adding prediction_score: {e}")
    
    try:
        # Add payment_behavior_history field to tenant_profiles table
        db.session.execute(text("""
            ALTER TABLE tenant_profiles 
            ADD COLUMN payment_behavior_history JSON NULL 
            COMMENT 'Historical payment behavior data for ML analysis'
        """))
        print("✓ Added payment_behavior_history to tenant_profiles")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("  - payment_behavior_history already exists")
        else:
            print(f"✗ Error adding payment_behavior_history: {e}")


def migrate_smart_notifications():
    """Add smart notification fields"""
    print("\nMigrating smart notification fields...")
    
    # Create notification_history table
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS notification_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                notification_type ENUM('payment_reminder', 'renewal_reminder', 'concern_alert', 'reservation_alert') NOT NULL,
                notification_priority ENUM('low', 'medium', 'high', 'urgent') NOT NULL,
                automated_trigger_type VARCHAR(100) NULL,
                message TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP NULL,
                status ENUM('sent', 'delivered', 'read', 'failed') DEFAULT 'sent',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) COMMENT='Smart notification history'
        """))
        print("✓ Created notification_history table")
    except Exception as e:
        if "already exists" in str(e):
            print("  - notification_history table already exists")
        else:
            print(f"✗ Error creating notification_history table: {e}")


def main():
    """Run all migrations"""
    print("=" * 60)
    print("AI Enhancements Database Migration")
    print("=" * 60)
    
    app = create_app()
    
    with app.app_context():
        migrate_identity_verification()
        migrate_nlp_chat()
        migrate_predictive_analytics()
        migrate_smart_notifications()
        
        db.session.commit()
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    main()
