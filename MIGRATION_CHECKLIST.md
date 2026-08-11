# ✅ SUPABASE MIGRATION CHECKLIST

Complete this checklist to ensure smooth migration. Check off each item as you complete it.

---

## 📋 PRE-MIGRATION

- [ ] XAMPP is running
- [ ] Can access phpMyAdmin (http://localhost/phpmyadmin)
- [ ] Current system is working
- [ ] Have Supabase account or ready to create one
- [ ] Have stable internet connection
- [ ] Read QUICK_MIGRATION.txt

---

## 💾 BACKUP (CRITICAL!)

- [ ] Export database from phpMyAdmin
- [ ] Saved as `stms_elis_backup.sql`
- [ ] File size looks reasonable (not 0 KB)
- [ ] Backup file is in safe location
- [ ] Copy .env to .env.backup manually (just in case)

**Location of backup:** _______________________

---

## 🌐 SUPABASE SETUP

- [ ] Created Supabase account at https://supabase.com
- [ ] Created new project named "ELIS System"
- [ ] Saved database password securely
- [ ] Project is fully initialized (green status)
- [ ] Got connection details from Settings → Database

**Supabase Project URL:** _______________________
**Database Host:** db._____________.supabase.co
**Database Password:** (saved securely) ✓

---

## 🔄 DATABASE CONVERSION

### Option A: Online Converter (Recommended)
- [ ] Went to https://www.sqlines.com/online
- [ ] Selected MySQL → PostgreSQL
- [ ] Uploaded stms_elis_backup.sql
- [ ] Downloaded converted file
- [ ] Saved as stms_elis_postgresql.sql

### Option B: Migration Script
- [ ] Ran: `python migrate_to_supabase.py`
- [ ] Followed all prompts
- [ ] Script completed without errors

**Converted file location:** _______________________

---

## 📤 IMPORT TO SUPABASE

- [ ] Opened Supabase SQL Editor
- [ ] Created New Query
- [ ] Copied entire converted SQL content
- [ ] Pasted into editor
- [ ] Ran query (Cmd/Ctrl + Enter)
- [ ] Waited for completion
- [ ] No red error messages
- [ ] Tables visible in Table Editor

**Number of tables imported:** _______

---

## 🔧 SYSTEM CONFIGURATION

- [ ] Installed PostgreSQL driver: `pip install psycopg2-binary`
- [ ] Created/Updated .env file with:
  - [ ] DB_TYPE=postgresql
  - [ ] DB_HOST=db.xxxxx.supabase.co
  - [ ] DB_PORT=5432
  - [ ] DB_NAME=postgres
  - [ ] DB_USER=postgres
  - [ ] DB_PASSWORD=(your password)
- [ ] Old .env backed up to .env.backup
- [ ] No typos in .env values
- [ ] File saved properly

---

## 🧪 TESTING

### Connection Test
- [ ] Ran: `python test_supabase_connection.py`
- [ ] TEST 1: Environment Config ✅
- [ ] TEST 2: PostgreSQL Driver ✅
- [ ] TEST 3: Raw Connection ✅
- [ ] TEST 4: SQLAlchemy ✅
- [ ] TEST 5: Models ✅
- [ ] TEST 6: Write Operations ✅

### Application Test
- [ ] Started: `python run.py`
- [ ] Server started without errors
- [ ] No database connection errors in terminal
- [ ] Opened http://localhost:5001
- [ ] Homepage loads
- [ ] Can see units

### Login Test
- [ ] Login page works
- [ ] Can login with admin account
- [ ] Can login with user account
- [ ] Dashboard loads after login

### Core Features Test
- [ ] Units page shows all units
- [ ] Can view unit details
- [ ] Can create reservation (if user)
- [ ] Admin can view reservations
- [ ] Admin can approve/reject
- [ ] Deposits page works
- [ ] User profile works

### Data Integrity Test
- [ ] Old users still exist
- [ ] Old reservations still visible
- [ ] Units data preserved
- [ ] Buildings data correct
- [ ] No data loss detected

---

## 🎉 POST-MIGRATION

- [ ] All tests passed
- [ ] System is stable
- [ ] Can perform all operations
- [ ] No errors in console
- [ ] Performance is acceptable

### Optional but Recommended
- [ ] Test for 24 hours before shutting down XAMPP
- [ ] Create a few test reservations
- [ ] Verify email notifications work (if configured)
- [ ] Test with different user roles
- [ ] Document any issues found

---

## 📚 DOCUMENTATION

- [ ] Updated team/personal notes about new database
- [ ] Shared Supabase credentials with team (securely)
- [ ] Documented any custom changes made
- [ ] Kept backup files in safe location
- [ ] Noted migration date: _______________

---

## 🔙 ROLLBACK PLAN (If Needed)

If something goes wrong, you can rollback:

- [ ] Stop application (Ctrl+C)
- [ ] Restore .env from .env.backup
- [ ] Change DB_TYPE=mysql in .env
- [ ] Start XAMPP
- [ ] Run: `python run.py`
- [ ] Verify old system works

**Keep backup files until you're 100% confident!**

---

## ⚠️ COMMON ISSUES & SOLUTIONS

### Issue: "Can't connect to database"
**Solution:**
- Check DB_PASSWORD in .env (no spaces, quotes)
- Verify DB_HOST is correct
- Test internet connection
- Make sure Supabase project is active

### Issue: "Import failed in SQL Editor"
**Solution:**
- Remove CREATE DATABASE statements
- Remove USE database statements
- Split into smaller chunks
- Check for syntax errors

### Issue: "Table doesn't exist"
**Solution:**
- Verify import completed
- Check Table Editor in Supabase
- Re-run import if needed
- Check for table name case sensitivity

### Issue: "Application crashes on startup"
**Solution:**
- Check all .env values
- Verify psycopg2-binary is installed
- Look at error message carefully
- Run test_supabase_connection.py

---

## 📊 PERFORMANCE COMPARISON

After migration, note any differences:

**Before (XAMPP MySQL):**
- Page load time: _______ seconds
- Query speed: _______

**After (Supabase PostgreSQL):**
- Page load time: _______ seconds  
- Query speed: _______

**Notes:** _______________________

---

## 🎯 SUCCESS CRITERIA

Your migration is successful when:

✅ All tests pass
✅ Application starts without errors
✅ Can login and perform all operations
✅ Data integrity verified (no missing records)
✅ Performance is acceptable
✅ No console errors during normal use

---

## 🚀 NEXT STEPS AFTER MIGRATION

Once everything is working:

1. **Keep XAMPP backup for 1 week** (just in case)
2. **Monitor for any issues** for a few days
3. **Update deployment docs** if any
4. **Consider enabling Supabase features:**
   - Real-time subscriptions
   - Row Level Security (RLS)
   - Automatic backups
   - API auto-generation

5. **Explore Supabase dashboard:**
   - View logs
   - Check performance
   - Set up monitoring
   - Configure alerts

---

## 📞 SUPPORT RESOURCES

- **Full Guide:** SUPABASE_MIGRATION_GUIDE.md
- **Quick Reference:** QUICK_MIGRATION.txt
- **Test Script:** python test_supabase_connection.py
- **Migration Tool:** python migrate_to_supabase.py
- **Supabase Docs:** https://supabase.com/docs
- **PostgreSQL Docs:** https://www.postgresql.org/docs/

---

**Migration Date:** _______________
**Completed By:** _______________
**Status:** ⬜ In Progress  ⬜ Completed  ⬜ Rolled Back
**Notes:** _______________________

---

## ✨ CONGRATULATIONS!

Once this checklist is complete, your ELIS System will be:
- ✅ Running on cloud database (Supabase)
- ✅ Accessible from anywhere
- ✅ Automatically backed up
- ✅ Using PostgreSQL (better performance)
- ✅ Ready for production deployment

**No more XAMPP needed! 🎉**
