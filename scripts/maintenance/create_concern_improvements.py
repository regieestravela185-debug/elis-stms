"""
Add new columns and table for concern improvements
"""
import mysql.connector
from mysql.connector import Error

def create_concern_improvements():
    connection = None
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='stms_elis',
            user='root',
            password=''
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Add new columns to concerns table
            alter_queries = [
                "ALTER TABLE concerns ADD COLUMN IF NOT EXISTS is_cancelled BOOLEAN NOT NULL DEFAULT FALSE",
                "ALTER TABLE concerns ADD COLUMN IF NOT EXISTS cancelled_at DATETIME NULL",
                "ALTER TABLE concerns ADD COLUMN IF NOT EXISTS resolved_at DATETIME NULL",
                "ALTER TABLE concerns ADD COLUMN IF NOT EXISTS in_progress_at DATETIME NULL",
                "ALTER TABLE concerns ADD COLUMN IF NOT EXISTS satisfaction_rating INT NULL",
                "ALTER TABLE concerns ADD COLUMN IF NOT EXISTS satisfaction_feedback TEXT NULL",
            ]
            
            for query in alter_queries:
                try:
                    cursor.execute(query)
                    print(f"✓ Executed: {query[:50]}...")
                except Error as e:
                    if "Duplicate column name" in str(e):
                        print(f"⊘ Column already exists, skipping...")
                    else:
                        print(f"✗ Error: {e}")
            
            # Create concern_follow_ups table
            create_table_query = """
            CREATE TABLE IF NOT EXISTS concern_follow_ups (
                id INT AUTO_INCREMENT PRIMARY KEY,
                concern_id INT NOT NULL,
                message TEXT NOT NULL,
                attachments_json TEXT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (concern_id) REFERENCES concerns(id) ON DELETE CASCADE,
                INDEX idx_concern_id (concern_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_table_query)
            print("✓ Created concern_follow_ups table")
            
            connection.commit()
            print("\n✅ All concern improvements applied successfully!")
            
    except Error as e:
        print(f"❌ Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    create_concern_improvements()
