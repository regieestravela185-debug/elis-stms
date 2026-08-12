# Collaboration Guide - ELIS STMS

## 🤝 Paano Mag-collaborate with Groupmates

### ❌ HUWAG GAWIN (Wrong Approach)
- ❌ Ibigay ang Render account password
- ❌ Ibigay ang Supabase account password
- ❌ I-share ang `.env` file na may secrets
- ❌ Mag-work sa iisang account

### ✅ DAPAT GAWIN (Correct Approach)
- ✅ Gumamit ng GitHub collaboration
- ✅ Bawat tao may sariling local development environment
- ✅ I-invite sa GitHub repository as collaborators
- ✅ Gumamit ng Git branches para sa features
- ✅ Code review before merge sa main branch

---

## 📋 Step-by-Step Guide

### STEP 1: Add Collaborators sa GitHub

**1. Go to your GitHub repository:**
```
https://github.com/regieestravela185-debug/elis-stms
```

**2. Click "Settings" (sa right side)**

**3. Click "Collaborators" sa left sidebar**

**4. Click "Add people" button**

**5. Search for groupmate's GitHub username or email**
```
Example:
- Username: juan_delaCruz
- Email: juan@gmail.com
```

**6. Click "Add [username] to this repository"**

**7. Groupmate will receive email invitation**

**8. Repeat para sa lahat ng groupmates**

---

### STEP 2: Groupmate's Setup (Local Development)

**Ito ang gagawin ng groupmate mo sa kanilang computer:**

#### A. Install Requirements
```bash
# 1. Install Python 3.11
# Download from: https://www.python.org/downloads/

# 2. Install Git
# Download from: https://git-scm.com/downloads

# 3. Install VS Code (optional but recommended)
# Download from: https://code.visualstudio.com/
```

#### B. Clone Repository
```bash
# 1. Accept GitHub invitation (check email)

# 2. Clone repository
git clone https://github.com/regieestravela185-debug/elis-stms.git

# 3. Enter directory
cd elis-stms

# 4. Create virtual environment
python -m venv .venv

# 5. Activate virtual environment
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 6. Install dependencies
pip install -r requirements.txt
```

#### C. Setup Local Environment

**Create `.env` file (HINDI mo i-share yung sa Render!):**

```bash
# Copy example file
cp .env.example .env
```

**Edit `.env` file:**
```env
# Flask
SECRET_KEY=local-dev-secret-key-change-this
DEBUG=1

# Local MySQL Database (XAMPP)
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=stms_elis_local
DB_USER=root
DB_PASSWORD=

# Email (Development - optional)
BREVO_API_KEY=your-personal-brevo-key
BREVO_SENDER_EMAIL=test@gmail.com

# Google OAuth (optional for local)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:5001/auth/google/callback
```

#### D. Setup Local Database

**Option 1: XAMPP (Recommended for beginners)**
```bash
# 1. Download XAMPP
# https://www.apachefriends.org/

# 2. Install and start Apache + MySQL

# 3. Open phpMyAdmin
# http://localhost/phpmyadmin

# 4. Create database: stms_elis_local

# 5. Import SQL file
# Import → Choose database/stms_elis_mysql.sql
```

**Option 2: PostgreSQL (Same as production)**
```bash
# 1. Install PostgreSQL
# https://www.postgresql.org/download/

# 2. Create database
createdb stms_elis_local

# 3. Update .env
DB_TYPE=postgresql
DB_PORT=5432
```

#### E. Run Development Server
```bash
# Make sure virtual environment is activated
# You should see (.venv) in terminal

# Run server
python run.py

# Open browser
# http://127.0.0.1:5001
```

---

### STEP 3: Workflow (Git Branches)

#### Para sa Bawat Feature/Task:

**1. Create new branch:**
```bash
# Get latest code
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/user-profile-page
```

**2. Work on your code:**
```bash
# Edit files...
# Test locally...
```

**3. Commit changes:**
```bash
# Check what changed
git status

# Add files
git add .

# Commit with message
git commit -m "feat: Add user profile page with edit functionality"
```

**4. Push to GitHub:**
```bash
git push origin feature/user-profile-page
```

**5. Create Pull Request:**
```
1. Go to GitHub repository
2. Click "Pull requests"
3. Click "New pull request"
4. Select your branch
5. Click "Create pull request"
6. Add description
7. Request review from groupmates
```

**6. Code Review:**
```
Groupmates will:
- Review code
- Leave comments
- Approve or request changes
```

**7. Merge:**
```
After approval:
1. Click "Merge pull request"
2. Delete branch
3. Render will auto-deploy
```

---

### STEP 4: Production Access (Render & Supabase)

#### ❌ Option 1: Share Accounts (NOT RECOMMENDED)
**Bakit hindi:**
- Security risk
- Di mo alam sino nag-change ng ano
- Pwedeng may mag-delete ng importante
- Mahirap i-track ang changes

#### ✅ Option 2: Add as Team Members (RECOMMENDED)

**Render:**
```
1. Login to Render
2. Go to Account Settings
3. Click "Teams" → "Create Team"
4. Invite groupmates by email
5. Set permissions:
   - "Member" - Can view and deploy
   - "Admin" - Full access
   - "Owner" - You lang dapat
```

**Supabase:**
```
1. Login to Supabase
2. Go to Project Settings
3. Click "Team" or "Members"
4. Invite by email
5. Set role:
   - "Read-only" - View only
   - "Developer" - Can edit tables
   - "Owner" - You lang dapat
```

#### ✅ Option 3: Shared Viewing Only
**Para sa thesis defense/presentation:**
```
1. Create READ-ONLY account
2. Share screen during meetings
3. Groupmates work on LOCAL only
4. Only YOU push to production
```

---

### STEP 5: Task Distribution

**Recommended division:**

**Person 1 (You - Project Lead):**
- Manage GitHub repository
- Review pull requests
- Deploy to production (Render)
- Manage database (Supabase)
- Security & monitoring

**Person 2 - Frontend:**
- Design UI/UX
- HTML/CSS templates
- JavaScript interactions
- Responsive design
- User experience

**Person 3 - Backend:**
- Python routes
- Database queries
- API endpoints
- Business logic
- Data validation

**Person 4 - Testing/Documentation:**
- Write test cases
- Test features
- Document code
- User manual
- Deployment guide

---

### STEP 6: Communication Setup

**1. Create Group Chat:**
```
- Telegram/Discord/Messenger
- Para sa quick questions
- Daily updates
```

**2. Use GitHub Issues:**
```
- Track bugs
- Feature requests
- Tasks assignment
- Progress tracking
```

**3. Weekly Meetings:**
```
- Code review
- Plan next sprint
- Resolve conflicts
- Share learnings
```

---

## 🔒 Security Best Practices

### Secrets Management

**❌ NEVER commit these files:**
```
.env
.env.local
*.key
credentials.json
```

**✅ Always in .gitignore:**
```bash
# Check .gitignore file
cat .gitignore

# Should contain:
.env
.env.*
!.env.example
```

**✅ Each developer has own secrets:**
```
- Own Brevo API key
- Own Google OAuth (for testing)
- Own local database
- Own SECRET_KEY
```

### Production Secrets

**Only YOU should have:**
- Render account login
- Supabase admin access
- Production API keys
- Production database credentials

**Store safely:**
- Use password manager (LastPass, 1Password)
- Never in group chat
- Never in email
- Never in shared documents

---

## 📝 Example Workflow

### Scenario: Add "View Reservations" Feature

**Week 1 - Planning:**
```
1. Create GitHub Issue
   Title: "Add View Reservations feature"
   Assign to: Person 3 (Backend)

2. Break down tasks:
   - Create database query
   - Create route/endpoint
   - Create HTML template
   - Add styling
   - Add tests
```

**Week 2 - Development:**
```
Person 3 (Backend):
1. git checkout -b feature/view-reservations
2. Create route in routes.py
3. Test locally
4. git commit -m "feat: Add reservations list endpoint"
5. git push origin feature/view-reservations
6. Create Pull Request

Person 2 (Frontend):
1. git checkout feature/view-reservations
2. Create HTML template
3. Add CSS styling
4. git commit -m "feat: Add reservations list UI"
5. git push origin feature/view-reservations
6. Update Pull Request
```

**Week 3 - Review & Deploy:**
```
You (Project Lead):
1. Review pull request
2. Test locally
3. Leave comments if needed
4. Approve and merge
5. Render auto-deploys
6. Test in production
7. Close GitHub Issue
```

---

## 🐛 Common Issues & Solutions

### Issue 1: Merge Conflicts
```bash
# Problem: Git says "merge conflict"

# Solution:
git checkout main
git pull origin main
git checkout your-branch
git merge main
# Fix conflicts in VS Code
git add .
git commit -m "fix: Resolve merge conflicts"
git push
```

### Issue 2: Can't Push to Main
```bash
# Problem: "protected branch" error

# Solution: 
# Don't push directly to main!
# Always use branches and pull requests
git checkout -b your-branch
git push origin your-branch
# Then create PR on GitHub
```

### Issue 3: Missing Packages
```bash
# Problem: "ModuleNotFoundError"

# Solution:
pip install -r requirements.txt
```

### Issue 4: Database Errors
```bash
# Problem: Can't connect to database

# Solution:
# 1. Check XAMPP is running
# 2. Check .env file
# 3. Check database exists
# 4. Re-import SQL file
```

---

## 📚 Learning Resources

**Git & GitHub:**
- Tutorial: https://www.youtube.com/watch?v=RGOj5yH7evk (Tagalog)
- Practice: https://learngitbranching.js.org/

**Python/Flask:**
- Flask Docs: https://flask.palletsprojects.com/
- Python Tutorial: https://www.w3schools.com/python/

**Collaboration:**
- GitHub Flow: https://guides.github.com/introduction/flow/
- Code Review: https://google.github.io/eng-practices/review/

---

## ✅ Checklist for Groupmates

**Before starting:**
- [ ] GitHub account created
- [ ] Accepted repository invitation
- [ ] Python 3.11 installed
- [ ] Git installed
- [ ] VS Code installed
- [ ] XAMPP installed
- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Local database setup
- [ ] .env file configured
- [ ] Server running successfully

**Development workflow:**
- [ ] Always create branch for new feature
- [ ] Test locally before pushing
- [ ] Write clear commit messages
- [ ] Create pull request (not direct push)
- [ ] Wait for code review
- [ ] Fix review comments
- [ ] Merge after approval

---

## 🎯 Summary

### What YOU control:
- ✅ GitHub repository (owner)
- ✅ Render deployment (your account)
- ✅ Supabase production database (your account)
- ✅ Production secrets & credentials
- ✅ Final merge to main branch

### What GROUPMATES can do:
- ✅ Clone repository
- ✅ Create branches
- ✅ Edit code locally
- ✅ Test on their computer
- ✅ Push to their branch
- ✅ Create pull requests
- ✅ Review each other's code

### What GROUPMATES cannot do:
- ❌ Push directly to main branch
- ❌ Delete production data
- ❌ Access your Render account
- ❌ Access your Supabase account
- ❌ Deploy to production (you do it via merge)

---

## 📞 Support

**If groupmates need help:**
1. Check this guide first
2. Search Google/Stack Overflow
3. Ask in group chat
4. Create GitHub Issue
5. Ask during meetings

**Emergency contacts:**
- Project Lead (You): [Your Phone]
- GitHub Issues: https://github.com/regieestravela185-debug/elis-stms/issues

---

**Good luck with your thesis! 🎓**

*Remember: Communication is key to successful collaboration!*
