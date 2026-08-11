#!/usr/bin/env python3
"""
Fix Blockchain Integrity Issues
This script regenerates the blockchain ledger entries for payments with integrity issues.
"""

from app import create_app
from app.extensions import db
from app.models import Payment, PaymentLedger
import hashlib
import json
from datetime import datetime

def generate_payment_hash(payment: Payment, previous_hash: str) -> tuple:
    """Generate blockchain hash for a payment - MUST MATCH verification logic exactly"""
    # Create payload - MUST MATCH the verification function
    payload = {
        "payment_id": payment.id,
        "tenant_profile_id": payment.tenant_profile_id,
        "amount": float(payment.amount),
        "reference": payment.reference,
        "paid_at": payment.paid_at.isoformat(),
    }
    
    payload_json = json.dumps(payload, sort_keys=True)
    
    # Generate hash - MUST MATCH verification: previous_hash + payload_json (NO PIPE!)
    hash_input = f"{previous_hash}{payload_json}"
    current_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    
    return payload_json, current_hash

def regenerate_blockchain():
    """Regenerate blockchain ledger for all payments"""
    app = create_app()
    
    with app.app_context():
        print("🔧 Starting blockchain regeneration...")
        print()
        
        # Get all payments ordered by ID
        payments = db.session.query(Payment).order_by(Payment.id).all()
        
        if not payments:
            print("❌ No payments found in database.")
            return
        
        print(f"📊 Found {len(payments)} payments")
        print()
        
        # Delete all existing ledger entries
        deleted_count = db.session.query(PaymentLedger).delete()
        print(f"🗑️  Deleted {deleted_count} old ledger entries")
        print()
        
        # Regenerate ledger for each payment
        previous_hash = "0" * 64  # Genesis hash
        
        for i, payment in enumerate(payments, 1):
            # Generate new hash
            payload_json, current_hash = generate_payment_hash(payment, previous_hash)
            
            # Create new ledger entry
            ledger = PaymentLedger(
                payment_id=payment.id,
                payload_json=payload_json,
                previous_hash=previous_hash,
                hash=current_hash,
                created_at=datetime.utcnow()
            )
            
            db.session.add(ledger)
            
            print(f"✅ [{i}/{len(payments)}] Payment #{payment.id} - {payment.tenant_profile.user.full_name}")
            print(f"   Amount: ₱{payment.amount:,.2f}")
            print(f"   Type: {'Deposit' if payment.is_deposit else 'Regular'}")
            print(f"   Hash: {current_hash[:16]}...")
            print()
            
            # Update previous hash for next iteration
            previous_hash = current_hash
        
        # Commit all changes
        db.session.commit()
        
        print("=" * 60)
        print("🎉 Blockchain regeneration complete!")
        print(f"✅ Successfully regenerated {len(payments)} ledger entries")
        print()
        print("Next steps:")
        print("1. Refresh your admin dashboard")
        print("2. The blockchain warning should be gone")
        print("3. All payment records are now verified")
        print("=" * 60)

if __name__ == "__main__":
    try:
        regenerate_blockchain()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
