"""
Migration script to add archive functionality to units table
Run this script to add is_archived, archived_at, and archived_by columns
"""
from app import create_app
from app.extensions import db

def migrate():
    app = create_app()
    
    with app.app_context():
        print("🔄 Starting migration: Adding archive columns to units table...")
        
        try:
            # Add columns using raw SQL
            with db.engine.connect() as conn:
                # Check if columns already exist
                result = conn.execute(db.text("""
                    SELECT COUNT(*) as count 
                    FROM information_schema.columns 
                    WHERE table_name='units' AND column_name='is_archived'
                """))
                
                exists = result.fetchone()[0] > 0
                
                if exists:
                    print("⚠️  Columns already exist. Skipping migration.")
                    return
                
                # Add is_archived column
                conn.execute(db.text("""
                    ALTER TABLE units 
                    ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE
                """))
                print("✅ Added is_archived column")
                
                # Add archived_at column
                conn.execute(db.text("""
                    ALTER TABLE units 
                    ADD COLUMN archived_at DATETIME NULL
                """))
                print("✅ Added archived_at column")
                
                # Add archived_by column
                conn.execute(db.text("""
                    ALTER TABLE units 
                    ADD COLUMN archived_by INTEGER NULL,
                    ADD FOREIGN KEY (archived_by) REFERENCES users(id)
                """))
                print("✅ Added archived_by column with foreign key")
                
                # Add updated_at column if it doesn't exist
                result = conn.execute(db.text("""
                    SELECT COUNT(*) as count 
                    FROM information_schema.columns 
                    WHERE table_name='units' AND column_name='updated_at'
                """))
                
                has_updated_at = result.fetchone()[0] > 0
                
                if not has_updated_at:
                    conn.execute(db.text("""
                        ALTER TABLE units 
                        ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    """))
                    print("✅ Added updated_at column")
                
                conn.commit()
                
            print("✅ Migration completed successfully!")
            print("\n📋 Summary:")
            print("   - is_archived: BOOLEAN (default: FALSE)")
            print("   - archived_at: DATETIME (nullable)")
            print("   - archived_by: INTEGER (foreign key to users.id)")
            print("   - updated_at: DATETIME (auto-update)")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate()
