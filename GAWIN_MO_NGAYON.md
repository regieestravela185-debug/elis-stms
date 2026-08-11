# ✅ GAWIN MO NGAYON - Supabase Setup

## 📍 Nandito ka na:
- ✅ Supabase project created
- ✅ Connection details complete
- ✅ Database file ready (22 tables)
- ✅ App code ready

## 🎯 5 STEPS LANG TO:

---

### **STEP 1: Import Database sa Supabase**

1. **Go to Supabase**
   - Buksan: https://supabase.com/dashboard
   - Login
   - Click project: **qthrznudzkgzrwvygmbd**

2. **Open SQL Editor**
   - Left sidebar → Click **"SQL Editor"**
   - Click **"New Query"** button

3. **Copy yung SQL file**
   - Open file: `database/stms_elis_postgresql_FULL.sql`
   - Select ALL (⌘+A or Ctrl+A)
   - Copy (⌘+C or Ctrl+C)

4. **Paste and Run**
   - Paste sa SQL Editor (⌘+V or Ctrl+V)
   - Click **"Run"** button (or press ⌘+Enter)

5. **⚠️ IMPORTANTE: Pag may lumabas na warning**
   ```
   ⚠️ Potential issues detected
   This query creates tables without enabling Row Level Security
   
   May 3 buttons:
   [Cancel] [Run without RLS] [Run and enable RLS]
   ```
   
   **👉 PINDUTIN: "Run without RLS"**
   
   ❓ Bakit "Run without RLS"?
   - Kasi ang app mo ay gumagamit ng Flask sessions para sa security
   - RLS (Row Level Security) is optional feature for extra security
   - Pwede mo i-enable later kung gusto mo
   - For now, hindi pa kailangan

6. **Wait for success**
   - May lalabas sa output:
   ```
   🎉 Database schema created successfully!
   ✅ Total tables: 22
   ✅ Seeded: 5 buildings, 6 users
   ```

7. **Check kung gumana**
   - Left sidebar → Click **"Table Editor"**
   - Dapat makita mo ang **22 tables**
   - Click `users` table → dapat may 6 users

---

### **STEP 2: Install PostgreSQL Driver**

Open terminal sa project folder:

```bash
pip install psycopg2-binary
```

**Kung nag-error**, try this:
```bash
pip install psycopg2
```

---

### **STEP 3: Update .env File**

Open `.env` file at i-update:

**I-add ang line na ito sa TOP:**
```env
DB_TYPE=postgresql
```

**Tapos i-comment yung MySQL settings at add Supabase:**
```env
# MySQL (XAMPP) - BACKUP LANG (comment muna)
# DB_HOST=127.0.0.1
# DB_PORT=3306
# DB_NAME=stms_elis
# DB_USER=root
# DB_PASSWORD=

# PostgreSQL (Supabase) - GAMITIN NA TO
DB_HOST=db.qthrznudzkgzrwvygmbd.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=Elis2026#123
```

**Save the file!**

---

### **STEP 4: Test Connection**

```bash
python test_supabase_connection.py
```

**Kung success, makikita mo:**
```
✅ Successfully connected to PostgreSQL!
✅ Database: postgres
✅ Version: PostgreSQL 15.x

Testing table count...
✅ Found 22 tables
  ✓ users
  ✓ activity_logs
  ✓ buildings
  ✓ units
  ... (lahat ng 22 tables)

✅ Connection test PASSED!
```

**Kung may error:**
- Check kung tama ang password sa `.env`: `Elis2026#123`
- Check kung naka-install na ang `psycopg2-binary`
- Check kung may `DB_TYPE=postgresql` sa `.env`

---

### **STEP 5: Run the App!**

```bash
python run.py
```

**Kung gumana, makikita mo:**
```
 * Running on http://127.0.0.1:5001
 * Database: PostgreSQL
 * Connected to: db.qthrznudzkgzrwvygmbd.supabase.co
```

**Test the app:**
1. Open browser: http://127.0.0.1:5001
2. Login as admin:
   - Email: `admin@gmail.com`
   - Password: `admin123`
3. Check dashboard - dapat makita mo ang data
4. Check reservations - dapat may laman
5. Try making a new reservation
6. Check sa Supabase Table Editor if nag-save

---

## 🎉 TAPOS NA!

Kung nag-work lahat ng yan, **SUCCESS!** 

Ang database mo ay nasa Supabase na ngayon at:
- ✅ No need na ng XAMPP
- ✅ Accessible from anywhere (kahit outside local network)
- ✅ Automatic backups
- ✅ Mas secure
- ✅ Always online

---

## 🔍 TROUBLESHOOTING

### ❌ Error: "No module named 'psycopg2'"
```bash
pip install psycopg2-binary
```

### ❌ Error: "Connection refused" or "Cannot connect"
- Check internet connection (Supabase is online)
- Check `.env` file - tama ba ang credentials?
- Check kung `DB_TYPE=postgresql` sa `.env`

### ❌ Error: "Role 'postgres' does not exist" or "Password authentication failed"
- Password mali - check kung `Elis2026#123` exactly
- Try reset password sa Supabase Dashboard → Settings → Database

### ❌ Error: "relation 'users' does not exist" or "Table not found"
- Tables hindi pa na-import
- Bumalik sa STEP 1 at i-run ulit ang SQL sa Supabase

### ❌ Dashboard walang data
- Check sa Supabase Table Editor kung may laman ang tables
- Kung walang laman, i-import ulit ang SQL file
- Check kung tama ang connection sa `.env`

---

## 📋 CHECKLIST

Gawin mo isa-isa:

- [ ] Import SQL sa Supabase SQL Editor
- [ ] Click "Run without RLS" pag may warning
- [ ] Verify 22 tables sa Table Editor
- [ ] Install `psycopg2-binary`
- [ ] Update `.env` with Supabase credentials
- [ ] Add `DB_TYPE=postgresql` sa `.env`
- [ ] Run `python test_supabase_connection.py`
- [ ] Run `python run.py`
- [ ] Login sa app
- [ ] Test lahat ng features
- [ ] Create test reservation
- [ ] Check data sa Supabase Table Editor

---

## 🎯 IMPORTANTE: Ang 22 Tables

Dapat makita mo sa Supabase lahat ng ito:

1. ✅ users
2. ✅ activity_logs
3. ✅ buildings
4. ✅ units
5. ✅ reservations
6. ✅ identity_verifications
7. ✅ tenant_profiles
8. ✅ payments
9. ✅ payment_ledger
10. ✅ concerns
11. ✅ concern_follow_ups
12. ✅ announcements
13. ✅ announcement_reads
14. ✅ documents
15. ✅ document_views
16. ✅ renewal_requests
17. ✅ feedbacks
18. ✅ chat_logs
19. ✅ inquiries
20. ✅ inquiry_replies
21. ✅ notification_history
22. ✅ blockchain_alarm_dismissal

---

## 📞 YOUR SUPABASE INFO

```
Project ID:  qthrznudzkgzrwvygmbd
Host:        db.qthrznudzkgzrwvygmbd.supabase.co
Port:        5432
Database:    postgres
User:        postgres
Password:    Elis2026#123
Region:      Singapore
```

**Connection String:**
```
postgresql://postgres:Elis2026#123@db.qthrznudzkgzrwvygmbd.supabase.co:5432/postgres
```

---

## ✅ SIGNS NG SUCCESS

1. ✅ `test_supabase_connection.py` → 22 tables found
2. ✅ `python run.py` → starts without errors
3. ✅ Can login to admin dashboard
4. ✅ Dashboard shows users, reservations, etc.
5. ✅ Can create new reservation
6. ✅ New data appears in Supabase Table Editor

---

**Kaya mo yan! Just follow the steps! 💪🚀**

Kung may problema, check ang troubleshooting section sa taas.
