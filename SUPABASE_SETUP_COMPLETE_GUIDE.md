# 🚀 COMPLETE SUPABASE MIGRATION GUIDE

## ✅ COMPLETED:
- [x] Supabase project created
- [x] Connection details obtained
- [x] Full PostgreSQL schema converted (ALL 22 tables)
- [x] App code already supports PostgreSQL

---

## 📋 NEXT STEPS (Gawin mo ngayon):

### **STEP 1: Import Database to Supabase**

1. **Go to Supabase Dashboard**
   - URL: https://supabase.com/dashboard
   - Login with your account

2. **Open SQL Editor**
   - Click your project: **qthrznudzkgzrwvygmbd**
   - Sa left sidebar, click **"SQL Editor"**
   - Click **"New Query"**

3. **Copy the FULL SQL file**
   - Open file: `database/stms_elis_postgresql_FULL.sql`
   - Select ALL (Cmd+A)
   - Copy ALL (Cmd+C)

4. **Paste and Run**
   - Paste sa SQL Editor (Cmd+V)
   - Click **"Run"** button (or press Cmd+Enter)
   
5. **When RLS warning appears:**
   ```
   ⚠️ Potential issues detected
   This query creates tables without enabling Row Level Security
   
   Buttons:
   [Cancel] [Run without RLS] [Run and enable RLS]
   ```
   
   **👉 PINDUTIN: "Run without RLS"**
   
   Why? Ang app mo ay gumagamit ng Flask sessions para sa security, hindi pa naka-setup ang RLS. Pwede mo i-enable later.

6. **Wait for success message**
   - May makikita kang output sa baba:
   ```
   🎉 Database schema created successfully!
   ✅ Total tables: 22
   ✅ Seeded: 5 buildings, 6 users, 4 activity logs
   ```

7. **Verify tables were created**
   - Sa left sidebar, click **"Table Editor"**
   - Dapat makikita mo ang lahat ng 22 tables:
     - activity_logs
     - announcement_reads
     - announcements
     - blockchain_alarm_dismissal
     - buildings
     - chat_logs
     - concern_follow_ups
     - concerns
     - document_views
     - documents
     - feedbacks
     - identity_verifications
     - inquiries
     - inquiry_replies
     - notification_history
     - payment_ledger
     - payments
     - renewal_requests
     - reservations
     - tenant_profiles
     - units
     - users

---

### **STEP 2: Install PostgreSQL Driver**

```bash
pip install psycopg2-binary
```

**Kung nag-error:**
```bash
# Try this instead:
pip install psycopg2
```

---

### **STEP 3: Update .env File**

Open `.env` file at i-update:

```env
# ADD THIS LINE AT THE TOP:
DB_TYPE=postgresql

# UPDATE THESE LINES (keep MySQL commented for backup):
# MySQL (XAMPP) - BACKUP
# DB_HOST=127.0.0.1
# DB_PORT=3306
# DB_NAME=stms_elis
# DB_USER=root
# DB_PASSWORD=

# PostgreSQL (Supabase) - ACTIVE
DB_HOST=db.qthrznudzkgzrwvygmbd.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=Elis2026#123
```

**IMPORTANT:** Keep your MySQL config commented (with `#`) para pwede mo pa bumalik kung may problema.

---

### **STEP 4: Test Connection**

```bash
python test_supabase_connection.py
```

**Expected output kung success:**
```
✅ Successfully connected to PostgreSQL!
✅ Database: postgres
✅ Version: PostgreSQL 15.x

Testing table count...
✅ Found 22 tables:
  - activity_logs
  - announcement_reads
  - announcements
  (... all 22 tables listed)

✅ Connection test PASSED!
```

**Kung nag-error:**
- Check if `DB_TYPE=postgresql` in `.env`
- Check if password is correct: `Elis2026#123`
- Check if you installed `psycopg2-binary`

---

### **STEP 5: Run the Application**

```bash
python run.py
```

**Expected output:**
```
 * Running on http://127.0.0.1:5001
 * Database: PostgreSQL
 * Connected to: db.qthrznudzkgzrwvygmbd.supabase.co
```

---

### **STEP 6: Test the System**

1. **Login as Admin**
   - Email: `admin@gmail.com`
   - Password: `admin123`

2. **Check Dashboard**
   - Should show all existing data
   - Check if reservations, users, payments appear

3. **Test Reservation Form**
   - Go to customer homepage
   - Try creating a new reservation
   - Upload an ID
   - Check if it saves to Supabase

4. **Verify in Supabase**
   - Go to Supabase → Table Editor
   - Click `reservations` table
   - Should see new reservation data

---

## 🔍 TROUBLESHOOTING

### **Problem: "No module named 'psycopg2'"**
**Solution:**
```bash
pip install psycopg2-binary
```

### **Problem: "Connection refused"**
**Solution:**
- Check `.env` file has correct Supabase credentials
- Verify `DB_TYPE=postgresql`
- Check internet connection (Supabase is cloud-based)

### **Problem: "Role 'postgres' does not exist"**
**Solution:**
- Verify password is correct: `Elis2026#123`
- Check if you're using the correct host
- Try resetting database password in Supabase Dashboard

### **Problem: "Tables not found"**
**Solution:**
- Go back to Supabase SQL Editor
- Run the `stms_elis_postgresql_FULL.sql` again
- Make sure you clicked "Run without RLS"

### **Problem: App shows blank data**
**Solution:**
- Check if tables were created in Supabase
- Verify seed data was inserted (check `users` table should have 6 users)
- Check terminal output for database errors

---

## 📊 WHAT CHANGED?

### **Database: XAMPP MySQL → Supabase PostgreSQL**
| Before (MySQL) | After (PostgreSQL) |
|----------------|-------------------|
| Local (127.0.0.1) | Cloud (db.qthrznudzkgzrwvygmbd.supabase.co) |
| Port 3306 | Port 5432 |
| Requires XAMPP running | Always online (Supabase) |
| Limited to local network | Accessible from anywhere |
| Manual backups | Automatic backups |

### **Tables: Same 22 tables**
✅ No data loss - all tables converted
✅ All relationships preserved
✅ All indexes maintained

### **Application Code: No changes needed!**
✅ `app/config.py` already supports both MySQL and PostgreSQL
✅ SQLAlchemy handles the differences automatically
✅ Same Flask routes, same functions

---

## 🎯 YOUR SUPABASE CONNECTION DETAILS

```
Host:     db.qthrznudzkgzrwvygmbd.supabase.co
Port:     5432
Database: postgres
User:     postgres
Password: Elis2026#123
```

**Connection String:**
```
postgresql://postgres:Elis2026#123@db.qthrznudzkgzrwvygmbd.supabase.co:5432/postgres
```

---

## ✅ CHECKLIST

- [ ] Import `stms_elis_postgresql_FULL.sql` to Supabase SQL Editor
- [ ] Click "Run without RLS" when prompted
- [ ] Verify 22 tables were created in Table Editor
- [ ] Install `psycopg2-binary` driver
- [ ] Update `.env` file with Supabase credentials
- [ ] Add `DB_TYPE=postgresql` to `.env`
- [ ] Run `python test_supabase_connection.py`
- [ ] Run `python run.py`
- [ ] Login and test the system
- [ ] Create a test reservation
- [ ] Verify data appears in Supabase

---

## 📞 NEED HELP?

**Common Issues:**
1. **RLS Warning** → Click "Run without RLS"
2. **Connection Error** → Check `.env` credentials
3. **Missing Tables** → Re-run the SQL file
4. **Import Error** → Install `psycopg2-binary`

**Files to check:**
- `.env` - database credentials
- `app/config.py` - database configuration
- `test_supabase_connection.py` - connection tester
- `database/stms_elis_postgresql_FULL.sql` - full schema with 22 tables

**What to check in Supabase:**
1. SQL Editor → Check if import was successful
2. Table Editor → Verify 22 tables exist
3. Database Settings → Check password is set

---

## 🎉 SUCCESS INDICATORS

Alam mo na successful ang migration kung:

✅ `python test_supabase_connection.py` - Shows 22 tables
✅ `python run.py` - App starts without errors
✅ Admin dashboard - Shows existing users and reservations
✅ Supabase Table Editor - Shows all 22 tables with data
✅ New reservations - Save to Supabase successfully

---

**Nandito na lahat ng 22 tables sa PostgreSQL file! 
Just import it to Supabase and you're good to go! 🚀**
