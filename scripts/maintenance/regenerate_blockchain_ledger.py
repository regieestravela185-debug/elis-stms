#!/usr/bin/env python
"""Regenerate blockchain ledger entries for all payments with normalized timestamps."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import create_app, db
from app.models import Payment, PaymentLedger

def regenerate_ledger():
    """Regenerate blockchain ledger entries for all payments."""
    app = create_app()
    
    with app.app_context():
        # Get all payments ordered by creation date
        payments = db.session.query(Payment).order_by(Payment.paid_at.asc()).all()
        
        print(f"Found {len(payments)} payments to regenerate ledger entries for.")
        
        # Clear existing ledger entries
        db.session.query(PaymentLedger).delete()
        db.session.commit()
        print("Cleared existing ledger entries.")
        
        # Import the ledger generation function
        from app.blueprints.admin.routes import _generate_payment_ledger
        
        # Generate new ledger entries
        for payment in payments:
            _generate_payment_ledger(payment)
            print(f"Generated ledger entry for payment ID {payment.id}")
        
        db.session.commit()
        print(f"Successfully regenerated {len(payments)} ledger entries.")

if __name__ == "__main__":
    regenerate_ledger()
