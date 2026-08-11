"""
Add new columns to payments table for improvements
"""
import mysql.connector
from mysql.connector import Error

def add_payment_improvements():
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
            
            # Add new columns to payments table
            alter_queries = [
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'verified'",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS is_late BOOLEAN DEFAULT FALSE",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS breakdown_json TEXT NULL",
                "ALTER TABLE payments ADD COLUMN IF NOT EXISTS receipt_number VARCHAR(50) NULL",
            ]
            
            for query in alter_queries:
                try:
                    cursor.execute(query)
                    print(f"✓ Executed: {query[:60]}...")
                except Error as e:
                    if "Duplicate column name" in str(e):
                        print(f"⊘ Column already exists, skipping...")
                    else:
                        print(f"✗ Error: {e}")
            
            connection.commit()
            print("\n✅ All payment improvements applied successfully!")
            
    except Error as e:
        print(f"❌ Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    add_payment_improvements()
