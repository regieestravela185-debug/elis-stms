# Quick Start Guide for Groupmates

## 🚀 5-Minute Setup

### 1️⃣ Accept GitHub Invitation
- Check your email
- Click "Accept invitation"
- You now have access to the code!

### 2️⃣ Install Required Software

**Windows:**
```
1. Python 3.11: https://www.python.org/downloads/
2. Git: https://git-scm.com/downloads  
3. XAMPP: https://www.apachefriends.org/
4. VS Code: https://code.visualstudio.com/
```

**Mac:**
```
1. Python 3.11: https://www.python.org/downloads/
2. Git: Already installed (check with: git --version)
3. XAMPP: https://www.apachefriends.org/
4. VS Code: https://code.visualstudio.com/
```

### 3️⃣ Clone & Setup

```bash
# 1. Open Terminal/Command Prompt
# 2. Go to your projects folder
cd Desktop

# 3. Clone repository
git clone https://github.com/regieestravela185-debug/elis-stms.git

# 4. Enter folder
cd elis-stms

# 5. Create virtual environment
python -m venv .venv

# 6. Activate it
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 7. Install packages (may take 2-3 minutes)
pip install -r requirements.txt
```

### 4️⃣ Setup Database

```bash
# 1. Start XAMPP
# - Open XAMPP Control Panel
# - Start "Apache"
# - Start "MySQL"

# 2. Open browser → http://localhost/phpmyadmin

# 3. Create database:
# - Click "New"
# - Database name: stms_elis_local
# - Click "Create"

# 4. Import data:
# - Select database "stms_elis_local"
# - Click "Import"
# - Choose file: database/stms_elis_mysql.sql
# - Click "Go"
```

### 5️⃣ Create .env File

```bash
# 1. Copy example
cp .env.example .env

# 2. Edit .env file (use Notepad or VS Code):
SECRET_KEY=my-local-dev-secret
DEBUG=1
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=stms_elis_local
DB_USER=root
DB_PASSWORD=
```

### 6️⃣ Run Server

```bash
# Make sure virtual environment is active (you should see (.venv))

python run.py

# You should see:
# * Running on http://127.0.0.1:5001
```

### 7️⃣ Open in Browser

```
http://127.0.0.1:5001
```

**You should see the ELIS STMS homepage!** 🎉

---

## 🔄 Daily Workflow

### Before You Start Work:

```bash
# 1. Get latest code
git checkout main
git pull origin main

# 2. Create your branch
git checkout -b feature/your-feature-name
# Example: git checkout -b feature/user-dashboard
```

### While Working:

```bash
# 1. Edit files in VS Code
# 2. Test in browser (http://127.0.0.1:5001)
# 3. Check what changed:
git status

# 4. See changes:
git diff
```

### When Done:

```bash
# 1. Add files
git add .

# 2. Commit
git commit -m "feat: Add user dashboard page"

# 3. Push to GitHub
git push origin feature/your-feature-name

# 4. Go to GitHub → Create Pull Request
# 5. Wait for review
# 6. Address comments if any
# 7. Get merged! 🎉
```

---

## 💡 Common Commands

```bash
# Check status
git status

# See what changed
git diff

# Discard changes
git checkout .

# Get latest code
git pull origin main

# See all branches
git branch -a

# Switch branch
git checkout branch-name

# Delete local branch
git branch -d branch-name
```

---

## 🆘 Help!

### Server won't start?
```bash
# Check Python version
python --version
# Should be 3.11.x

# Check virtual environment
which python
# Should show path with .venv

# Reinstall packages
pip install -r requirements.txt
```

### Database error?
```bash
# Check XAMPP is running
# Check .env file has correct settings
# Re-import database
```

### Can't push to GitHub?
```bash
# Never push directly to main!
# Always use branches

# Create branch first:
git checkout -b your-branch

# Then push:
git push origin your-branch
```

---

## 📞 Get Help

1. **Read full guide:** `COLLABORATION_GUIDE.md`
2. **Ask in group chat**
3. **Create GitHub Issue**
4. **Google the error message**
5. **Ask project lead**

---

## ✅ Checklist

- [ ] GitHub invitation accepted
- [ ] Python 3.11 installed
- [ ] Git installed
- [ ] XAMPP installed
- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Packages installed
- [ ] Database created
- [ ] Database imported
- [ ] .env file created
- [ ] Server running
- [ ] Can open http://127.0.0.1:5001

**If all checked, you're ready to code!** 🚀

---

## 🎓 Branch Naming Convention

```bash
# Features
git checkout -b feature/reservation-list
git checkout -b feature/tenant-dashboard

# Bug fixes
git checkout -b fix/login-error
git checkout -b fix/database-connection

# UI improvements
git checkout -b ui/improve-homepage
git checkout -b ui/mobile-responsive

# Documentation
git checkout -b docs/update-readme
git checkout -b docs/add-comments
```

---

## 📝 Commit Message Format

```bash
# Good examples:
git commit -m "feat: Add reservation list page"
git commit -m "fix: Resolve login validation error"
git commit -m "ui: Improve mobile responsiveness"
git commit -m "docs: Update installation guide"

# Bad examples:
git commit -m "update"  ❌ Too vague
git commit -m "asdf"    ❌ Meaningless
git commit -m "fixes"   ❌ What fixes?
```

**Format:** `type: Brief description`

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `ui:` - UI/UX changes
- `docs:` - Documentation
- `style:` - Code formatting
- `refactor:` - Code restructure
- `test:` - Add tests
- `chore:` - Maintenance

---

**Happy coding! 🎉**
