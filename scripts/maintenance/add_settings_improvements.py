"""
Migration script to add email preferences and password tracking to tenant_profiles table
"""

import mysql.connector
from mysql.connector import Error

def run_migration():
    try:
        # Connect to database
        connection = mysql.connector.connect(
            host='localhost',
            database='stms_elis',
            user='root',
            password=''
        )

        if connection.is_connected():
            cursor = connection.cursor()
            print("Connected to MySQL database")

            # Add email preferences columns
            migrations = [
                """
                ALTER TABLE tenant_profiles 
                ADD COLUMN IF NOT EXISTS email_announcements BOOLEAN NOT NULL DEFAULT TRUE
                """,
                """
                ALTER TABLE tenant_profiles 
                ADD COLUMN IF NOT EXISTS email_payment_reminders BOOLEAN NOT NULL DEFAULT TRUE
                """,
                """
                ALTER TABLE tenant_profiles 
                ADD COLUMN IF NOT EXISTS email_concern_updates BOOLEAN NOT NULL DEFAULT TRUE
                """,
                """
                ALTER TABLE tenant_profiles 
                ADD COLUMN IF NOT EXISTS password_changed_at DATETIME NULL
                """
            ]

            for migration in migrations:
                try:
                    cursor.execute(migration)
                    print(f"✓ Executed: {migration[:80]}...")
                except Error as e:
                    if "Duplicate column name" in str(e):
                        print(f"⊘ Column already exists, skipping...")
                    else:
                        print(f"✗ Error: {e}")

            connection.commit()
            print("\n✅ Migration completed successfully!")

    except Error as e:
        print(f"❌ Error connecting to MySQL: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed")

if __name__ == "__main__":
    print("Starting migration: Add settings improvements to tenant_profiles")
    print("=" * 70)
    run_migration()
