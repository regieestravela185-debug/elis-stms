#!/usr/bin/env python3
"""
Create sample feedback data for testing
"""

from app import create_app
from app.extensions import db
from app.models import Feedback, FeedbackStatus, TenantProfile
from datetime import datetime, timedelta
import random

def create_sample_feedbacks():
    app = create_app()
    
    with app.app_context():
        print("Creating sample feedback data...")
        print("=" * 80)
        
        # Get all active tenants
        tenants = db.session.query(TenantProfile).filter(
            TenantProfile.is_active == True
        ).limit(20).all()
        
        if not tenants:
            print("❌ No active tenants found. Please create tenants first.")
            return
        
        print(f"Found {len(tenants)} active tenants")
        
        # Categories
        categories = [
            'building_services',
            'maintenance',
            'security',
            'cleanliness',
            'staff_service',
            'facilities',
            'general'
        ]
        
        # Sample comments by rating
        comments_by_rating = {
            5: [
                "Excellent service! Very satisfied with the management and facilities.",
                "The staff is very helpful and responsive. Highly recommend!",
                "Great building with amazing amenities. Worth every peso!",
                "Very professional management. All concerns are addressed promptly.",
                "Clean, safe, and well-maintained. Perfect place to live!"
            ],
            4: [
                "Good overall experience. Minor issues but quickly resolved.",
                "Satisfied with the service. Could improve on response time.",
                "Nice facilities and friendly staff. Keep up the good work!",
                "Generally happy with everything. Some room for improvement.",
                "Good value for money. Management is doing a great job."
            ],
            3: [
                "Average experience. Some things need improvement.",
                "Okay naman but there are areas that need attention.",
                "Decent service but could be better in some aspects.",
                "Fair enough. Hope to see improvements soon.",
                "Not bad but not great either. Room for improvement."
            ],
            2: [
                "Disappointed with the slow response to maintenance requests.",
                "Several issues that need immediate attention.",
                "Not satisfied with the cleanliness of common areas.",
                "Poor communication from management. Needs improvement.",
                "Expected better service for the price we're paying."
            ],
            1: [
                "Very disappointed. Multiple unresolved issues.",
                "Terrible experience. Management is unresponsive.",
                "Worst service ever. Nothing gets fixed on time.",
                "Extremely dissatisfied. Considering moving out.",
                "Unacceptable service. Many problems not addressed."
            ]
        }
        
        # Admin responses
        admin_responses = [
            "Thank you for your feedback! We're glad you're satisfied with our service.",
            "We appreciate your input and will work on improving our response time.",
            "Thank you for bringing this to our attention. We'll address this immediately.",
            "We apologize for the inconvenience. Our team is working on resolving this.",
            "Your feedback is valuable to us. We'll make sure to improve in this area.",
            "Thank you for your patience. We're committed to providing better service.",
            "We're sorry to hear about your experience. Let's discuss this further.",
            "Thank you for the positive feedback! We'll continue to maintain our standards."
        ]
        
        created_count = 0
        
        # Create 30 sample feedbacks
        for i in range(30):
            tenant = random.choice(tenants)
            category = random.choice(categories)
            
            # 60% chance of having a rating
            has_rating = random.random() < 0.6
            rating = None
            comments = ""
            
            if has_rating:
                # Distribution: 40% 5-star, 30% 4-star, 15% 3-star, 10% 2-star, 5% 1-star
                rand = random.random()
                if rand < 0.40:
                    rating = 5
                elif rand < 0.70:
                    rating = 4
                elif rand < 0.85:
                    rating = 3
                elif rand < 0.95:
                    rating = 2
                else:
                    rating = 1
                
                comments = random.choice(comments_by_rating[rating])
            else:
                # No rating, just general comments
                comments = random.choice([
                    "Just wanted to share some suggestions for improvement.",
                    "General feedback about the building facilities.",
                    "Some observations I'd like to share with management.",
                    "Feedback regarding recent changes in the building.",
                    "Comments about the overall tenant experience."
                ])
            
            # Random date within last 60 days
            days_ago = random.randint(0, 60)
            created_at = datetime.utcnow() - timedelta(days=days_ago)
            
            # 70% chance of being reviewed
            is_reviewed = random.random() < 0.7
            status = FeedbackStatus.REVIEWED if is_reviewed else FeedbackStatus.SUBMITTED
            
            feedback = Feedback(
                tenant_profile_id=tenant.id,
                category=category,
                rating=rating,
                comments=comments,
                status=status,
                created_at=created_at
            )
            
            # Add admin response if reviewed
            if is_reviewed:
                feedback.admin_response = random.choice(admin_responses)
                feedback.admin_response_at = created_at + timedelta(hours=random.randint(1, 48))
                feedback.admin_response_by = 1  # Assuming admin user ID is 1
            
            db.session.add(feedback)
            created_count += 1
        
        db.session.commit()
        
        print(f"✓ Created {created_count} sample feedbacks")
        print()
        
        # Show summary
        total = db.session.query(Feedback).count()
        submitted = db.session.query(Feedback).filter(Feedback.status == FeedbackStatus.SUBMITTED).count()
        reviewed = db.session.query(Feedback).filter(Feedback.status == FeedbackStatus.REVIEWED).count()
        
        print("Summary:")
        print(f"  Total Feedbacks: {total}")
        print(f"  Submitted (Unreviewed): {submitted}")
        print(f"  Reviewed: {reviewed}")
        print()
        
        for i in range(5, 0, -1):
            count = db.session.query(Feedback).filter(Feedback.rating == i).count()
            print(f"  {'⭐' * i} ({i}): {count} feedbacks")
        
        no_rating = db.session.query(Feedback).filter(Feedback.rating.is_(None)).count()
        print(f"  No Rating: {no_rating} feedbacks")
        print()
        print("🎉 Sample feedback data created successfully!")
        print("=" * 80)

if __name__ == "__main__":
    create_sample_feedbacks()
