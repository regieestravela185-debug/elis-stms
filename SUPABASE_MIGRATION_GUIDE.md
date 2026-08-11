# 🚀 Supabase Migration Guide

Complete guide to migrate your ELIS System from XAMPP MySQL to Supabase PostgreSQL.

---

## 📋 Prerequisites

1. **Supabase Account** - Create at https://supabase.com
2. **Your XAMPP Database** - Make sure it's running with current data
3. **Backup** - Export your current database first!

---

## Step 1: Export Current MySQL Database

### Using phpMyAdmin (XAMPP):
1. Open http://localhost/phpmyadmin
2. Select database: `stms_elis`
3. Click "Export" tab
4. Choose "Quick" export method
5. Format: SQL
6. Click "Go" to download `stms_elis.sql`

### Or using Command Line:
```bash
# Navigate to XAMPP MySQL bin folder
cd /Applications/XAMPP/xamppfiles/bin  # Mac
# or
cd C:\xampp\mysql\bin  # Windows

# Export database
./mysqldump -u root -p stms_elis > ~/Desktop/stms_elis_backup.sql
```

**⚠️ IMPORTANT: Save this backup file safely!**

---

## Step 2: Create Supabase Project

1. Go to https://app.supabase.com
2. Click "New Project"
3. Fill in:
   - **Name**: ELIS System
   - **Database Password**: (strong password, save it!)
   - **Region**: Choose closest to Philippines (Singapore/Tokyo)
4. Click "Create new project"
5. Wait 2-3 minutes for setup

---

## Step 3: Get Supabase Connection Details

Once project is ready:

1. Click **Settings** (gear icon) → **Database**
2. Scroll to **Connection string** section
3. Copy the following info:
   - **Host**: `db.xxxxx.supabase.co`
   - **Port**: `5432`
   - **Database**: `postgres`
   - **User**: `postgres`
   - **Password**: (the one you set earlier)

**Example Connection String:**
```
postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

---

## Step 4: Convert MySQL to PostgreSQL

### Option A: Using Online Converter (Easiest)

1. Go to: https://www.sqlines.com/online
2. Select: MySQL → PostgreSQL
3. Upload your `stms_elis.sql` file
4. Click "Convert"
5. Download the converted `.sql` file

### Option B: Manual Conversion

Common changes needed:

**MySQL → PostgreSQL conversions:**
```sql
# 1. AUTO_INCREMENT → SERIAL
MySQL:  id INT AUTO_INCREMENT PRIMARY KEY
PG:     id SERIAL PRIMARY KEY

# 2. DATETIME → TIMESTAMP
MySQL:  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
PG:     created_at TIMESTAMP DEFAULT NOW()

# 3. TINYINT → SMALLINT or BOOLEAN
MySQL:  is_active TINYINT(1)
PG:     is_active BOOLEAN

# 4. Backticks → Double quotes (or remove)
MySQL:  `table_name`
PG:     "table_name" or table_name

# 5. ENGINE=InnoDB → Remove
MySQL:  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
PG:     (remove this completely)
```

---

## Step 5: Import to Supabase

### Using Supabase SQL Editor:

1. In Supabase Dashboard, go to **SQL Editor**
2. Click "New Query"
3. Paste your converted PostgreSQL SQL
4. Click "Run" (or Cmd/Ctrl + Enter)
5. Wait for import to complete

### Using psql Command Line:

```bash
# Install PostgreSQL client if needed
brew install postgresql  # Mac
# or download from postgresql.org for Windows

# Connect and import
psql "postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres" < converted_schema.sql
```

---

## Step 6: Update ELIS System Configuration

### 1. Update `requirements.txt`:

Add PostgreSQL driver:
```txt
# Replace pymysql with psycopg2
psycopg2-binary==2.9.9
```

Remove or comment out:
```txt
# PyMySQL==1.1.1  # Not needed for PostgreSQL
```

### 2. Update `app/config.py`:

Replace the database configuration section:

```python
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    # Supabase PostgreSQL Configuration
    DB_TYPE = os.getenv("DB_TYPE", "postgresql")  # mysql or postgresql
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "postgres")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # Dynamic connection string based on DB type
    if DB_TYPE == "postgresql":
        SQLALCHEMY_DATABASE_URI = (
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # ... rest of config
```

### 3. Update `.env` file:

```env
FLASK_ENV=production
SECRET_KEY=your-super-secret-key-here-change-this

# Supabase PostgreSQL
DB_TYPE=postgresql
DB_HOST=db.xxxxx.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your-supabase-db-password

# Rest of your config...
UPLOAD_FOLDER=app/static/uploads
MAX_CONTENT_LENGTH_MB=10
```

### 4. Install new dependencies:

```bash
# Activate virtual environment
source .venv/bin/activate  # Mac/Linux
# or
.venv\Scripts\activate  # Windows

# Install PostgreSQL driver
pip install psycopg2-binary==2.9.9

# Or reinstall all requirements
pip install -r requirements.txt
```

---

## Step 7: Update SQL Queries in Code

### Check for MySQL-specific syntax:

1. **LIMIT/OFFSET** - Same in both ✅
2. **IF NOT EXISTS** - Same in both ✅
3. **Boolean values**:
   ```python
   # MySQL accepts 0/1
   # PostgreSQL prefers TRUE/FALSE
   # SQLAlchemy handles this automatically ✅
   ```

4. **Date functions** - Already using SQLAlchemy ORM ✅

### Update Schema Migrations (`app/__init__.py`):

Replace MySQL-specific DDL with PostgreSQL compatible:

```python
def _apply_non_breaking_schema_updates() -> None:
    """Best-effort additive schema updates for local/dev runs."""
    
    # PostgreSQL uses IF NOT EXISTS differently
    stmts = [
        # Use ALTER TABLE ... ADD COLUMN IF NOT EXISTS (PostgreSQL 9.6+)
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS id_type VARCHAR(64)",
        "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS id_number VARCHAR(120)",
        "ALTER TABLE units ADD COLUMN IF NOT EXISTS description TEXT",
        "ALTER TABLE units ADD COLUMN IF NOT EXISTS unit_images_json TEXT",
        # ... rest of your statements
    ]
    
    for stmt in stmts:
        try:
            db.session.execute(text(stmt))
            db.session.commit()
        except Exception:
            db.session.rollback()
```

---

## Step 8: Test the Migration

### 1. Test Database Connection:

```bash
# Run Python shell
python

# Test connection
>>> from app import create_app, db
>>> app = create_app()
>>> with app.app_context():
...     db.engine.connect()
...     print("✅ Connected to Supabase!")
```

### 2. Test Basic Queries:

```python
# In Python shell
>>> from app import create_app, db
>>> from app.models import User, Unit
>>> app = create_app()
>>> with app.app_context():
...     users = User.query.all()
...     print(f"Found {len(users)} users")
...     units = Unit.query.all()
...     print(f"Found {len(units)} units")
```

### 3. Start the Application:

```bash
python run.py
# or
./start.sh
```

Visit http://localhost:5001 and test:
- ✅ Login
- ✅ View units
- ✅ Create reservation
- ✅ Admin dashboard

---

## Step 9: Supabase Real-time Features (Optional)

### Enable Real-time for Tables:

1. In Supabase Dashboard → **Database** → **Replication**
2. Enable replication for tables you want real-time:
   - `reservations`
   - `units`
   - `users`
3. Click **Enable** for each table

### Add Real-time Subscriptions (Future Enhancement):

```javascript
// Using Supabase JS Client
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

// Subscribe to reservation changes
supabase
  .channel('reservations')
  .on('postgres_changes', 
    { event: '*', schema: 'public', table: 'reservations' },
    (payload) => {
      console.log('Reservation updated!', payload)
      // Update UI in real-time
    }
  )
  .subscribe()
```

---

## Step 10: Deploy to Production (Optional)

### Supabase Advantages:
- ✅ Always online (no need for XAMPP)
- ✅ Automatic backups
- ✅ SSL/TLS encryption
- ✅ Connection pooling
- ✅ Real-time subscriptions
- ✅ Free tier: 500MB database, 2GB bandwidth

### Deploy Application:
- **Heroku**: Free tier available
- **Railway**: Easy deployment
- **Render**: Free tier for web services
- **Vercel/Netlify**: For static frontend

---

## 🔧 Troubleshooting

### Connection Issues:

```python
# Test connection
import psycopg2
conn = psycopg2.connect(
    host="db.xxxxx.supabase.co",
    port=5432,
    database="postgres",
    user="postgres",
    password="your-password"
)
print("✅ Connected!")
conn.close()
```

### SSL Certificate Error:

Add to connection string:
```python
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?sslmode=require"
)
```

### Import Errors:

If import fails, check:
1. Character encoding issues
2. Foreign key constraints order
3. Enum type definitions

---

## 📊 Comparison: XAMPP vs Supabase

| Feature | XAMPP (Local) | Supabase (Cloud) |
|---------|--------------|------------------|
| **Availability** | Computer must be on | Always online 24/7 |
| **Backups** | Manual | Automatic daily |
| **Access** | Local network only | Internet (secure) |
| **Performance** | Local speed | Depends on internet |
| **Cost** | Free | Free tier available |
| **Scalability** | Limited | Automatic scaling |
| **Real-time** | Manual polling | Built-in real-time |
| **Security** | Basic | SSL, row-level security |

---

## ✅ Final Checklist

- [ ] Backup current MySQL database
- [ ] Create Supabase project
- [ ] Convert MySQL → PostgreSQL schema
- [ ] Import to Supabase
- [ ] Install psycopg2-binary
- [ ] Update config.py
- [ ] Update .env with Supabase credentials
- [ ] Test database connection
- [ ] Test all CRUD operations
- [ ] Test file uploads
- [ ] Test user login/registration
- [ ] Test admin functions
- [ ] Verify real-time features work

---

## 📞 Need Help?

Common issues:
- **Can't connect**: Check firewall, VPN, or IP whitelist in Supabase
- **Import fails**: Convert schema properly (AUTO_INCREMENT → SERIAL)
- **Data missing**: Check import logs in SQL Editor
- **Slow queries**: Add indexes in Supabase dashboard

**Supabase Docs**: https://supabase.com/docs
**PostgreSQL Docs**: https://www.postgresql.org/docs/

---

## 🎉 Benefits After Migration

1. ✅ **No XAMPP needed** - Database always online
2. ✅ **Real-time updates** - See changes instantly
3. ✅ **Automatic backups** - Never lose data
4. ✅ **Remote access** - Work from anywhere
5. ✅ **Free SSL** - Secure connections
6. ✅ **API auto-generated** - REST & GraphQL ready
7. ✅ **Better performance** - Optimized PostgreSQL
8. ✅ **Easy scaling** - Grows with your app

Good luck with the migration! 🚀
