#!/usr/bin/env python3
"""
Migration: Add unit_id to feedbacks table for easier unit-specific rating queries
This allows us to directly query feedbacks by unit without joining through tenant_profile
"""

from app import create_app
from app.extensions import db
from app.models import Feedback, TenantProfile

def migrate_add_unit_id():
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("MIGRATION: Add unit_id to feedbacks table")
        print("=" * 80)
        print()
        
        # Check if column already exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('feedbacks')]
        
        if 'unit_id' in columns:
            print("✓ Column 'unit_id' already exists in feedbacks table")
            print()
        else:
            print("Adding 'unit_id' column to feedbacks table...")
            
            # Add column using raw SQL
            with db.engine.connect() as conn:
                conn.execute(db.text("""
                    ALTER TABLE feedbacks 
                    ADD COLUMN unit_id INT NULL,
                    ADD FOREIGN KEY (unit_id) REFERENCES units(id)
                """))
                conn.commit()
            
            print("✓ Column 'unit_id' added successfully")
            print()
        
        # Populate unit_id for existing feedbacks
        print("Populating unit_id for existing feedbacks...")
        
        feedbacks = db.session.query(Feedback).all()
        updated_count = 0
        
        for feedback in feedbacks:
            if feedback.unit_id is None and feedback.tenant_profile:
                feedback.unit_id = feedback.tenant_profile.unit_id
                updated_count += 1
        
        db.session.commit()
        
        print(f"✓ Updated {updated_count} feedbacks with unit_id")
        print()
        
        # Verify
        print("Verification:")
        total_feedbacks = db.session.query(Feedback).count()
        feedbacks_with_unit = db.session.query(Feedback).filter(Feedback.unit_id.isnot(None)).count()
        
        print(f"  Total feedbacks: {total_feedbacks}")
        print(f"  Feedbacks with unit_id: {feedbacks_with_unit}")
        
        if total_feedbacks == feedbacks_with_unit:
            print("  ✓ All feedbacks have unit_id")
        else:
            print(f"  ⚠ {total_feedbacks - feedbacks_with_unit} feedbacks missing unit_id")
        
        print()
        print("=" * 80)
        print("MIGRATION COMPLETE!")
        print("=" * 80)

if __name__ == "__main__":
    migrate_add_unit_id()
