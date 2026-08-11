# 🐙 GitHub Setup Guide - Para sa Team Collaboration

Quick guide para sa pag-setup ng GitHub repository at collaboration with your groupmates.

---

## 🚀 Part 1: I-Push ang Code sa GitHub

### Step 1: Check kung may git na
```bash
cd /Users/regie-302004/Desktop/ElisSystem
git status
```

Kung may error, gawin mo yung git init:
```bash
git init
```

### Step 2: Create GitHub Repository

1. **Pumunta sa GitHub:** https://github.com/new
2. **Repository name:** `elis-stms` (o kahit ano)
3. **Description:** "Smart Tenant Management System - Flask + Supabase"
4. **Visibility:** 
   - **Private** - kung gusto mo only groupmates can see
   - **Public** - kung okay lang na makita ng lahat
5. **WAG i-check** ang "Initialize with README" (may README ka na)
6. **Click** "Create repository"

### Step 3: Connect at Push

GitHub will show commands, pero eto simplified version:

```bash
# Add all files
git add .

# First commit
git commit -m "Initial commit - ELIS STMS"

# Connect to GitHub (replace YOUR-USERNAME and YOUR-REPO)
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**Example:**
```bash
git remote add origin https://github.com/regie-302004/elis-stms.git
git push -u origin main
```

---

## 👥 Part 2: Add Your Groupmates

### Step 1: Invite Collaborators

1. Go to your GitHub repository
2. Click **"Settings"** tab (sa taas)
3. Click **"Collaborators"** (sa left sidebar)
4. Click **"Add people"** button
5. Enter groupmate's GitHub username or email
6. Click **"Add [username] to this repository"**
7. They'll receive an email invitation

### Step 2: Groupmates Accept Invitation

Your groupmates need to:
1. Check their email
2. Click the invitation link
3. Click "Accept invitation"
4. They now have access! 🎉

---

## 💻 Part 3: Groupmates Setup (Local Development)

### Step 1: Install Python 3.12.6

**macOS/Linux:**
```bash
# Check current version
python3 --version

# If not 3.12.6, install via:
# - Official Python.org website
# - Or use pyenv (recommended)
```

**Windows:**
1. Download Python 3.12.6 from python.org
2. Run installer
3. ✅ Check "Add Python to PATH"
4. Click "Install Now"

### Step 2: Clone Repository

```bash
# Clone the repo (replace with actual URL)
git clone https://github.com/YOUR-USERNAME/elis-stms.git

# Enter directory
cd elis-stms
```

### Step 3: Create Virtual Environment

**macOS/Linux:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

You'll see `(.venv)` in your terminal = success! ✅

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

This might take 2-5 minutes ⏱️

### Step 5: Setup Environment Variables

```bash
# Copy example env file
cp .env.example .env
```

**macOS/Linux:**
```bash
cp .env.example .env
```

**Windows:**
```bash
copy .env.example .env
```

Then **edit `.env` file** with actual values:
- Supabase credentials
- Gmail credentials
- Google OAuth credentials
- Secret key

**Ask the repository owner for the actual credentials!** 🔐

### Step 6: Run the Application

```bash
python run.py
```

Open browser: `http://127.0.0.1:5000`

If successful, you'll see the ELIS homepage! 🎉

---

## 🔄 Part 4: Daily Development Workflow

### Basic Git Commands

#### 1. Before Starting Work (Get Latest Code)
```bash
git pull origin main
```

#### 2. Make Changes
- Edit files
- Add new features
- Fix bugs

#### 3. Check What Changed
```bash
git status
```

#### 4. Stage and Commit Changes
```bash
# Stage specific files
git add app/blueprints/admin/routes.py
git add app/templates/admin/dashboard.html

# Or stage all changes
git add .

# Commit with meaningful message
git commit -m "Add monthly report feature to admin dashboard"
```

#### 5. Push to GitHub
```bash
git push origin main
```

### ⚠️ Important Rules

**ALWAYS pull before push:**
```bash
git pull origin main
git push origin main
```

**Write clear commit messages:**
```bash
✅ Good: "Fix login bug - handle empty email validation"
✅ Good: "Add unit filter to admin deposits page"
❌ Bad: "update"
❌ Bad: "fix stuff"
```

---

## 🌿 Part 5: Using Branches (Advanced)

Para hindi mag-conflict ang code, use branches:

### Create Feature Branch
```bash
# Create and switch to new branch
git checkout -b feature/payment-reports

# Work on your feature...
git add .
git commit -m "Add payment reports feature"

# Push branch to GitHub
git push origin feature/payment-reports
```

### Create Pull Request
1. Go to GitHub repository
2. Click "Pull requests" tab
3. Click "New pull request"
4. Select your branch
5. Click "Create pull request"
6. Add description
7. Request review from teammate
8. After approval, click "Merge pull request"

### Switch Between Branches
```bash
# Go back to main
git checkout main

# Go to feature branch
git checkout feature/payment-reports

# List all branches
git branch
```

---

## 🔧 Part 6: Common Issues & Solutions

### Issue: "Permission denied"
**Cause:** Hindi ka pa collaborator
**Solution:** Ask repository owner to add you as collaborator

### Issue: "Merge conflict"
**Cause:** Dalawa kayo nag-edit ng same file
**Solution:**
```bash
git pull origin main
# Manually edit conflicted files
git add .
git commit -m "Resolve merge conflict"
git push origin main
```

### Issue: ".env file not found"
**Cause:** Hindi naka-copy ang .env.example
**Solution:**
```bash
cp .env.example .env
# Then edit .env with actual credentials
```

### Issue: "Module not found"
**Cause:** Hindi naka-install ang dependencies
**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: "Database connection failed"
**Cause:** Wrong credentials in .env
**Solution:** Ask repository owner for correct Supabase credentials

---

## 📝 Part 7: Team Workflow Example

### Scenario: 3 Team Members

**Member 1 (You):** Main developer, repository owner
**Member 2:** Working on admin features
**Member 3:** Working on tenant features

### Workflow:

#### Member 1 (Repository Owner):
```bash
# Setup repo
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR-USERNAME/elis-stms.git
git push -u origin main

# Add collaborators on GitHub Settings
```

#### Member 2 (Admin Features):
```bash
# Clone repo
git clone https://github.com/YOUR-USERNAME/elis-stms.git
cd elis-stms

# Setup environment
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with credentials

# Create feature branch
git checkout -b feature/admin-reports

# Work on admin reports
# ... edit files ...

# Commit and push
git add .
git commit -m "Add monthly revenue report to admin dashboard"
git push origin feature/admin-reports

# Create Pull Request on GitHub
```

#### Member 3 (Tenant Features):
```bash
# Clone repo
git clone https://github.com/YOUR-USERNAME/elis-stms.git
cd elis-stms

# Setup environment (same as Member 2)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Create feature branch
git checkout -b feature/tenant-payments

# Work on tenant payment history
# ... edit files ...

# Commit and push
git add .
git commit -m "Add payment history page for tenants"
git push origin feature/tenant-payments

# Create Pull Request on GitHub
```

#### Member 1 (Review & Merge):
1. Go to GitHub repository
2. Check Pull Requests
3. Review Member 2's PR
4. If good, click "Merge pull request"
5. Review Member 3's PR
6. If good, click "Merge pull request"
7. Everyone pulls latest changes:
```bash
git checkout main
git pull origin main
```

---

## 🎓 Git Cheat Sheet

```bash
# Clone repository
git clone <repo-url>

# Check status
git status

# Pull latest changes
git pull origin main

# Stage changes
git add .                    # All files
git add file.py             # Specific file

# Commit changes
git commit -m "Message"

# Push changes
git push origin main

# Create branch
git checkout -b feature-name

# Switch branch
git checkout branch-name

# List branches
git branch

# Delete branch
git branch -d feature-name

# View commit history
git log

# Discard local changes
git checkout -- file.py
```

---

## 🔐 Security Reminders

**NEVER commit these files:**
- `.env` ✅ Already in .gitignore
- `__pycache__/` ✅ Already in .gitignore
- `.venv/` ✅ Already in .gitignore
- Database files ✅ Already in .gitignore

**Always use .env for sensitive data:**
- Database passwords
- Email passwords
- API keys
- Secret keys

**Share credentials securely:**
- Use encrypted messages
- Use password managers
- Never post in public channels

---

## ✅ Quick Checklist for Groupmates

- [ ] GitHub account created
- [ ] Accepted repository invitation
- [ ] Python 3.12.6 installed
- [ ] Git installed
- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` file created with credentials
- [ ] Application runs locally
- [ ] Can pull and push to GitHub

---

## 🎉 You're Ready!

Your team can now collaborate effectively on the ELIS STMS project!

**Best Practices:**
✅ Pull before you start working
✅ Commit frequently with clear messages
✅ Use branches for new features
✅ Create Pull Requests for review
✅ Test before pushing
✅ Communicate with your team

---

*Happy Coding! 🚀*
