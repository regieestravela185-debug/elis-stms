"""
Script to distribute units across 4 floors (1, 2, 3, 4)
Run this script to update existing units in the database.
"""

import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Unit

def update_units_floors():
    """Update units to distribute them across floors 1, 2, 3, 4"""
    app = create_app()
    
    with app.app_context():
        # Get all non-archived units
        units = Unit.query.filter(Unit.is_archived == False).all()
        
        print(f"Found {len(units)} units in the database")
        
        # Distribute units across floors 1, 2, 3, 4
        floor_assignments = [1, 2, 3, 4]
        
        for i, unit in enumerate(units):
            # Cycle through floors 1, 2, 3, 4
            new_floor = floor_assignments[i % len(floor_assignments)]
            
            print(f"Updating unit {unit.unit_code} from floor {unit.floor} to floor {new_floor}")
            unit.floor = new_floor
        
        # Commit the changes
        try:
            db.session.commit()
            print("\n✓ Successfully updated all units to floors 1, 2, 3, 4")
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error updating units: {e}")
            return False
        
        return True

if __name__ == "__main__":
    if update_units_floors():
        print("\nUnits have been distributed across floors 1, 2, 3, 4")
        print("Check the homepage and floorplan to see the changes.")
    else:
        print("\nFailed to update units. Please check the error above.")
