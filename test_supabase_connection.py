#!/usr/bin/env python3
"""
Test Supabase Connection
Run this after migration to verify everything works
"""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def test_env_config():
    """Test if .env is configured for Supabase"""
    print("="*60)
    print("TEST 1: Checking .env Configuration")
    print("="*60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    db_type = os.getenv("DB_TYPE")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    
    print(f"DB_TYPE: {db_type}")
    print(f"DB_HOST: {db_host}")
    print(f"DB_PORT: {db_port}")
    print(f"DB_NAME: {db_name}")
    print(f"DB_USER: {db_user}")
    print(f"DB_PASSWORD: {'*' * len(db_password) if db_password else 'NOT SET'}")
    
    if db_type == "postgresql" and "supabase.co" in (db_host or ""):
        print("\n✅ Configuration looks good for Supabase!")
        return True
    elif db_type == "mysql":
        print("\n⚠️  Still configured for MySQL. Update .env file:")
        print("   DB_TYPE=postgresql")
        print("   DB_HOST=db.xxxxx.supabase.co")
        return False
    else:
        print("\n❌ Configuration incomplete!")
        return False


def test_psycopg2():
    """Test if PostgreSQL driver is installed"""
    print("\n" + "="*60)
    print("TEST 2: Checking PostgreSQL Driver")
    print("="*60)
    
    try:
        import psycopg2
        print(f"✅ psycopg2 version: {psycopg2.__version__}")
        return True
    except ImportError:
        print("❌ psycopg2 not installed!")
        print("\nInstall with:")
        print("   pip install psycopg2-binary")
        return False


def test_raw_connection():
    """Test raw PostgreSQL connection"""
    print("\n" + "="*60)
    print("TEST 3: Testing Raw Database Connection")
    print("="*60)
    
    try:
        import psycopg2
        from dotenv import load_dotenv
        load_dotenv()
        
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            sslmode='require',
            connect_timeout=10
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        
        cursor.execute("SELECT current_database();")
        db = cursor.fetchone()
        
        print(f"✅ Connected to PostgreSQL!")
        print(f"Database: {db[0]}")
        print(f"Version: {version[0][:80]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check DB_HOST in .env")
        print("2. Verify DB_PASSWORD is correct")
        print("3. Ensure Supabase project is active")
        print("4. Check internet connection")
        return False


def test_sqlalchemy_connection():
    """Test SQLAlchemy connection"""
    print("\n" + "="*60)
    print("TEST 4: Testing SQLAlchemy Connection")
    print("="*60)
    
    try:
        from app import create_app, db
        
        app = create_app()
        
        with app.app_context():
            # Test connection
            result = db.session.execute(db.text("SELECT 1"))
            print("✅ SQLAlchemy connected!")
            
            # Check tables exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"✅ Found {len(tables)} tables:")
            for table in sorted(tables)[:10]:  # Show first 10
                print(f"   - {table}")
            if len(tables) > 10:
                print(f"   ... and {len(tables) - 10} more")
            
            return True
            
    except Exception as e:
        print(f"❌ SQLAlchemy connection failed: {e}")
        return False


def test_models():
    """Test if models can query data"""
    print("\n" + "="*60)
    print("TEST 5: Testing Models")
    print("="*60)
    
    try:
        from app import create_app, db
        from app.models import User, Unit, Building, Reservation
        
        app = create_app()
        
        with app.app_context():
            # Test User model
            user_count = User.query.count()
            print(f"✅ Users table: {user_count} records")
            
            # Test Building model
            building_count = Building.query.count()
            print(f"✅ Buildings table: {building_count} records")
            
            # Test Unit model
            unit_count = Unit.query.count()
            print(f"✅ Units table: {unit_count} records")
            
            # Test Reservation model
            reservation_count = Reservation.query.count()
            print(f"✅ Reservations table: {reservation_count} records")
            
            print("\n✅ All models working!")
            return True
            
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        print("\nThis might mean:")
        print("1. Tables not imported to Supabase yet")
        print("2. Table structure doesn't match models")
        return False


def test_create_record():
    """Test if we can create a record"""
    print("\n" + "="*60)
    print("TEST 6: Testing Write Operations")
    print("="*60)
    
    try:
        from app import create_app, db
        from app.models import Building
        from datetime import datetime
        
        app = create_app()
        
        with app.app_context():
            # Try to create a test building
            test_building = Building(
                code="TEST_BUILD",
                name="Test Building",
                address="Test Address",
                floors=5,
                created_at=datetime.utcnow()
            )
            
            db.session.add(test_building)
            db.session.flush()
            
            # Get the ID
            building_id = test_building.id
            print(f"✅ Created test building (ID: {building_id})")
            
            # Delete it (cleanup)
            db.session.delete(test_building)
            db.session.commit()
            print("✅ Cleanup successful")
            
            print("\n✅ Write operations working!")
            return True
            
    except Exception as e:
        print(f"❌ Write test failed: {e}")
        db.session.rollback()
        return False


def main():
    print("\n" + "🚀 ELIS SYSTEM - SUPABASE CONNECTION TEST ".center(60, "="))
    print()
    
    results = []
    
    # Run all tests
    results.append(("Environment Config", test_env_config()))
    results.append(("PostgreSQL Driver", test_psycopg2()))
    results.append(("Raw Connection", test_raw_connection()))
    results.append(("SQLAlchemy", test_sqlalchemy_connection()))
    results.append(("Models", test_models()))
    results.append(("Write Operations", test_create_record()))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print("\n" + "="*60)
    if passed_count == total_count:
        print("🎉 ALL TESTS PASSED!")
        print("="*60)
        print("\nYour system is ready to use Supabase!")
        print("\nNext steps:")
        print("1. Run: python run.py")
        print("2. Open: http://localhost:5001")
        print("3. Test the application normally")
    else:
        print(f"⚠️  {total_count - passed_count} TEST(S) FAILED")
        print("="*60)
        print("\nPlease fix the failed tests before proceeding.")
        print("See SUPABASE_MIGRATION_GUIDE.md for help.")
    
    return passed_count == total_count


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
