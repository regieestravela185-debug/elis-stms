#!/usr/bin/env python3
"""
ELIS System - Supabase Migration Helper
This script helps you migrate from MySQL to PostgreSQL (Supabase)
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")


def print_step(number, text):
    print(f"\n{'='*60}")
    print(f"STEP {number}: {text}")
    print(f"{'='*60}\n")


def check_dependencies():
    """Check if required packages are installed"""
    print("Checking dependencies...")
    
    try:
        import pymysql
        print("✅ PyMySQL installed")
    except ImportError:
        print("❌ PyMySQL not installed")
        return False
    
    try:
        import psycopg2
        print("✅ psycopg2 installed")
    except ImportError:
        print("⚠️  psycopg2 not installed - will install later")
    
    return True


def install_postgresql_driver():
    """Install PostgreSQL driver"""
    print_step(1, "Installing PostgreSQL Driver")
    
    print("Installing psycopg2-binary...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary==2.9.9"])
        print("\n✅ PostgreSQL driver installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("\n❌ Failed to install psycopg2-binary")
        print("Try manually: pip install psycopg2-binary")
        return False


def export_mysql_schema():
    """Export current MySQL database schema"""
    print_step(2, "Exporting MySQL Database")
    
    print("This will export your current database structure and data.")
    print("\nOptions:")
    print("1. Use phpMyAdmin (Recommended for beginners)")
    print("2. Use mysqldump command line")
    
    choice = input("\nChoose option (1 or 2): ").strip()
    
    if choice == "1":
        print("\n📋 Follow these steps:")
        print("1. Open http://localhost/phpmyadmin in your browser")
        print("2. Click on 'stms_elis' database")
        print("3. Click 'Export' tab at the top")
        print("4. Choose 'Quick' export method")
        print("5. Format: SQL")
        print("6. Click 'Go' button")
        print("7. Save the file as 'stms_elis_backup.sql'")
        
        input("\n✅ Press Enter when you've completed the export...")
        
        # Check if file exists
        backup_file = Path.home() / "Downloads" / "stms_elis_backup.sql"
        if backup_file.exists():
            print(f"\n✅ Found backup at: {backup_file}")
            return str(backup_file)
        else:
            custom_path = input("\nEnter the full path to your exported SQL file: ").strip()
            if Path(custom_path).exists():
                return custom_path
            else:
                print("❌ File not found. Please try again.")
                return None
    
    elif choice == "2":
        print("\n⚠️  This requires MySQL command line tools")
        output_file = Path.home() / "Desktop" / "stms_elis_backup.sql"
        
        cmd = f"mysqldump -u root -p stms_elis > {output_file}"
        print(f"\nRun this command in your terminal:\n{cmd}")
        
        input("\n✅ Press Enter when done...")
        
        if output_file.exists():
            print(f"\n✅ Backup created at: {output_file}")
            return str(output_file)
        else:
            print("❌ Backup file not found")
            return None
    
    return None


def convert_to_postgresql():
    """Guide for converting MySQL to PostgreSQL"""
    print_step(3, "Converting MySQL to PostgreSQL")
    
    print("We need to convert MySQL syntax to PostgreSQL syntax.\n")
    print("Choose conversion method:")
    print("1. Online converter (Easy - Recommended)")
    print("2. Manual conversion (Advanced)")
    
    choice = input("\nChoose option (1 or 2): ").strip()
    
    if choice == "1":
        print("\n📋 Online Conversion Steps:")
        print("1. Go to: https://www.sqlines.com/online")
        print("2. Select: MySQL → PostgreSQL")
        print("3. Upload your 'stms_elis_backup.sql' file")
        print("4. Click 'Convert'")
        print("5. Download the converted file")
        print("6. Save it as 'stms_elis_postgresql.sql'")
        
        input("\n✅ Press Enter when conversion is complete...")
        
        converted_file = input("Enter path to converted PostgreSQL file: ").strip()
        if Path(converted_file).exists():
            print(f"\n✅ Conversion file ready: {converted_file}")
            return converted_file
        else:
            print("❌ File not found")
            return None
    
    else:
        print("\n📋 Manual Conversion Guide:")
        print("\nCommon replacements needed:")
        print("1. AUTO_INCREMENT → SERIAL")
        print("2. DATETIME → TIMESTAMP")
        print("3. TINYINT(1) → BOOLEAN")
        print("4. Remove ENGINE=InnoDB")
        print("5. Remove DEFAULT CHARSET=utf8mb4")
        print("6. Change ` backticks to \" quotes (or remove)")
        
        print("\nFor detailed guide, see SUPABASE_MIGRATION_GUIDE.md")
        
        input("\n✅ Press Enter when manual conversion is complete...")
        
        converted_file = input("Enter path to your PostgreSQL SQL file: ").strip()
        if Path(converted_file).exists():
            return converted_file
        else:
            print("❌ File not found")
            return None


def setup_supabase_project():
    """Guide for setting up Supabase"""
    print_step(4, "Setting Up Supabase Project")
    
    print("📋 Create your Supabase project:")
    print("\n1. Go to: https://supabase.com")
    print("2. Sign up or login")
    print("3. Click 'New Project'")
    print("4. Fill in:")
    print("   - Name: ELIS System")
    print("   - Database Password: (create a strong password)")
    print("   - Region: Singapore or Tokyo (closest to Philippines)")
    print("5. Click 'Create new project'")
    print("6. Wait 2-3 minutes for setup")
    
    input("\n✅ Press Enter when project is ready...")
    
    print("\n📋 Get your connection details:")
    print("1. In Supabase dashboard, click 'Settings' (gear icon)")
    print("2. Click 'Database' in left sidebar")
    print("3. Scroll to 'Connection string' section")
    print("4. Note down these details:")
    
    print("\n" + "-"*60)
    db_host = input("Enter DB Host (db.xxxxx.supabase.co): ").strip()
    db_password = input("Enter DB Password: ").strip()
    print("-"*60)
    
    return {
        'host': db_host,
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': db_password
    }


def import_to_supabase(converted_file, db_config):
    """Guide for importing to Supabase"""
    print_step(5, "Importing to Supabase")
    
    print("📋 Import your database:")
    print("\n1. In Supabase dashboard, go to 'SQL Editor' (left sidebar)")
    print("2. Click 'New Query'")
    print(f"3. Open this file in a text editor: {converted_file}")
    print("4. Copy ALL the SQL content")
    print("5. Paste it into the Supabase SQL Editor")
    print("6. Click 'Run' (or press Cmd/Ctrl + Enter)")
    print("7. Wait for import to complete (may take a few minutes)")
    
    print("\n⚠️  If you get errors:")
    print("   - Remove any CREATE DATABASE statements")
    print("   - Remove any USE database statements")
    print("   - Try running in smaller chunks")
    
    input("\n✅ Press Enter when import is complete...")
    
    # Verify
    verify = input("\nDid the import complete successfully? (yes/no): ").strip().lower()
    return verify == 'yes'


def update_env_file(db_config):
    """Update .env file with Supabase config"""
    print_step(6, "Updating Configuration")
    
    env_path = Path(".env")
    backup_path = Path(".env.backup")
    
    # Backup current .env
    if env_path.exists():
        print(f"Creating backup: {backup_path}")
        env_path.rename(backup_path)
    
    # Read backup or create new
    env_content = []
    if backup_path.exists():
        with open(backup_path) as f:
            for line in f:
                # Skip old DB config
                if not any(line.startswith(prefix) for prefix in ['DB_TYPE=', 'DB_HOST=', 'DB_PORT=', 'DB_NAME=', 'DB_USER=', 'DB_PASSWORD=']):
                    env_content.append(line.rstrip())
    
    # Add new Supabase config at the top
    new_config = [
        "# Supabase PostgreSQL Configuration",
        "DB_TYPE=postgresql",
        f"DB_HOST={db_config['host']}",
        f"DB_PORT={db_config['port']}",
        f"DB_NAME={db_config['database']}",
        f"DB_USER={db_config['user']}",
        f"DB_PASSWORD={db_config['password']}",
        ""
    ]
    
    # Write new .env
    with open(env_path, 'w') as f:
        f.write('\n'.join(new_config))
        f.write('\n')
        f.write('\n'.join(env_content))
    
    print(f"\n✅ Updated {env_path}")
    print(f"✅ Old config backed up to {backup_path}")


def test_connection(db_config):
    """Test database connection"""
    print_step(7, "Testing Connection")
    
    print("Testing connection to Supabase...")
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password'],
            sslmode='require'
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        
        print(f"\n✅ Connection successful!")
        print(f"PostgreSQL version: {version[0][:50]}...")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if host is correct (db.xxxxx.supabase.co)")
        print("2. Verify password is correct")
        print("3. Make sure Supabase project is active")
        print("4. Check your internet connection")
        return False


def test_application():
    """Test the application"""
    print_step(8, "Testing Application")
    
    print("Let's test your application with Supabase!\n")
    print("Starting the application...")
    
    print("\n📋 Run these commands in your terminal:")
    print("\n1. Start the server:")
    print("   python run.py")
    print("\n2. Open browser: http://localhost:5001")
    print("\n3. Test these features:")
    print("   ✓ Login page loads")
    print("   ✓ Can login with existing account")
    print("   ✓ Units page shows units")
    print("   ✓ Can view reservations")
    print("   ✓ Admin dashboard works")
    
    input("\n✅ Press Enter when testing is complete...")
    
    all_working = input("\nDid everything work correctly? (yes/no): ").strip().lower()
    return all_working == 'yes'


def main():
    print_header("🚀 ELIS System - Supabase Migration Tool")
    
    print("This tool will help you migrate from MySQL (XAMPP) to Supabase (PostgreSQL)")
    print("\n⚠️  IMPORTANT:")
    print("- Make sure XAMPP is running")
    print("- Have your Supabase account ready")
    print("- This process takes about 15-30 minutes")
    
    proceed = input("\nReady to start? (yes/no): ").strip().lower()
    if proceed != 'yes':
        print("\n👋 Migration cancelled. Come back when ready!")
        return
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Missing dependencies. Please install requirements first.")
        return
    
    # Step 1: Install PostgreSQL driver
    if not install_postgresql_driver():
        return
    
    # Step 2: Export MySQL
    backup_file = export_mysql_schema()
    if not backup_file:
        print("\n❌ Export failed. Please try again.")
        return
    
    # Step 3: Convert to PostgreSQL
    converted_file = convert_to_postgresql()
    if not converted_file:
        print("\n❌ Conversion failed. Please try again.")
        return
    
    # Step 4: Setup Supabase
    db_config = setup_supabase_project()
    if not db_config or not db_config['host']:
        print("\n❌ Supabase setup incomplete.")
        return
    
    # Step 5: Import to Supabase
    if not import_to_supabase(converted_file, db_config):
        print("\n❌ Import failed. Check Supabase SQL Editor for errors.")
        return
    
    # Step 6: Update .env
    update_env_file(db_config)
    
    # Step 7: Test connection
    if not test_connection(db_config):
        print("\n❌ Connection test failed. Check your configuration.")
        return
    
    # Step 8: Test application
    if test_application():
        print_header("🎉 MIGRATION COMPLETE!")
        print("\n✅ Your ELIS System is now running on Supabase!")
        print("\nNext steps:")
        print("1. Test all features thoroughly")
        print("2. Keep your .env.backup file safe")
        print("3. You can now stop XAMPP")
        print("\n📚 See SUPABASE_MIGRATION_GUIDE.md for more details")
    else:
        print("\n⚠️  Migration complete but testing found issues.")
        print("Check the guide for troubleshooting steps.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Migration interrupted. You can run this script again anytime.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nFor help, check SUPABASE_MIGRATION_GUIDE.md")
