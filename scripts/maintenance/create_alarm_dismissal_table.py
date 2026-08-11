#!/usr/bin/env python3
"""
Create blockchain_alarm_dismissal table to track when admin stops the alarm
"""

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Creating blockchain_alarm_dismissal table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS blockchain_alarm_dismissal (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        dismissed_at DATETIME NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    try:
        db.session.execute(db.text(sql))
        db.session.commit()
        print("✓ Table created successfully")
    except Exception as e:
        print(f"✗ Error: {e}")
        db.session.rollback()
