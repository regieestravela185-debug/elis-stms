#!/usr/bin/env python3
"""
Automatic Renewal Reminder Scheduler
Run this script daily to send renewal reminders to tenants with expiring contracts.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import TenantProfile, Unit
from app.blueprints.admin.routes import _send_renewal_reminder_email
from datetime import date, timedelta
from sqlalchemy import text

def ensure_database_field():
    """Add last_renewal_reminder_sent field to tenant_profiles table if it doesn't exist"""
    try:
        # Check if column exists
        result = db.session.execute(text("PRAGMA table_info(tenant_profiles)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'last_renewal_reminder_sent' not in columns:
            print("Adding last_renewal_reminder_sent field to tenant_profiles...")
            db.session.execute(text("""
                ALTER TABLE tenant_profiles 
                ADD COLUMN last_renewal_reminder_sent DATE
            """))
            db.session.commit()
            print("✓ Field added successfully")
        else:
            print("✓ Field already exists")
    except Exception as e:
        print(f"Error adding field: {e}")
        db.session.rollback()

def send_automatic_reminders():
    """Send renewal reminders to tenants with expiring contracts"""
    app = create_app()
    
    with app.app_context():
        # Ensure database field exists
        ensure_database_field()
        
        today = date.today()
        threshold = today + timedelta(days=60)
        reminder_cooldown = today - timedelta(days=30)
        
        # Find tenants with contracts expiring in 60 days or less
        # AND haven't received a reminder in the last 30 days
        expiring_tenants = db.session.query(TenantProfile).filter(
            TenantProfile.contract_end.isnot(None),
            TenantProfile.contract_end <= threshold,
            TenantProfile.contract_end > today,
            TenantProfile.is_active == True,
            db.or_(
                TenantProfile.last_renewal_reminder_sent == None,
                TenantProfile.last_renewal_reminder_sent < reminder_cooldown
            )
        ).all()
        
        reminders_sent = 0
        print(f"\n{'='*50}")
        print(f"Automatic Renewal Reminder - {today.strftime('%B %d, %Y')}")
        print(f"{'='*50}")
        print(f"Checking for contracts expiring within 60 days...")
        
        for profile in expiring_tenants:
            days_remaining = (profile.contract_end - today).days
            unit = db.session.get(Unit, profile.unit_id)
            
            if unit and profile.user:
                print(f"\nSending reminder to: {profile.user.full_name}")
                print(f"  Unit: {unit.unit_code}")
                print(f"  Contract ends: {profile.contract_end.strftime('%B %d, %Y')}")
                print(f"  Days remaining: {days_remaining}")
                
                _send_renewal_reminder_email(
                    tenant_name=profile.user.full_name,
                    tenant_email=profile.user.email,
                    unit_code=unit.unit_code,
                    contract_end=profile.contract_end,
                    days_remaining=days_remaining
                )
                profile.last_renewal_reminder_sent = today
                reminders_sent += 1
                print("  ✓ Email sent")
        
        if reminders_sent > 0:
            db.session.commit()
            print(f"\n{'='*50}")
            print(f"✓ Successfully sent {reminders_sent} reminder(s)")
            print(f"{'='*50}")
        else:
            print(f"\n{'='*50}")
            print("No reminders to send today")
            print(f"{'='*50}")

if __name__ == "__main__":
    send_automatic_reminders()
