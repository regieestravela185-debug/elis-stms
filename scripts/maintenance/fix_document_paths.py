#!/usr/bin/env python
"""Fix document file paths in database"""

from app import create_app
from app.extensions import db
from app.models import Document

app = create_app()

with app.app_context():
    # Get all documents
    documents = db.session.query(Document).all()
    
    print(f"Found {len(documents)} documents")
    
    fixed_count = 0
    for doc in documents:
        old_path = doc.file_path
        
        # Fix paths that start with 'app/uploads/' or 'app/static/uploads/'
        if doc.file_path.startswith('app/uploads/'):
            doc.file_path = doc.file_path.replace('app/uploads/', 'uploads/')
            fixed_count += 1
            print(f"✅ Fixed: {old_path} → {doc.file_path}")
        elif doc.file_path.startswith('app/static/uploads/'):
            doc.file_path = doc.file_path.replace('app/static/uploads/', 'uploads/')
            fixed_count += 1
            print(f"✅ Fixed: {old_path} → {doc.file_path}")
        elif doc.file_path.startswith('static/uploads/'):
            doc.file_path = doc.file_path.replace('static/uploads/', 'uploads/')
            fixed_count += 1
            print(f"✅ Fixed: {old_path} → {doc.file_path}")
        else:
            print(f"✓ OK: {doc.file_path}")
    
    if fixed_count > 0:
        db.session.commit()
        print(f"\n✅ Fixed {fixed_count} document paths!")
    else:
        print("\n✓ All paths are correct!")
