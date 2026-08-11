# 🚀 Push to GitHub - Copy & Paste Commands

Ito yung commands para ma-push ang code mo sa GitHub. **Copy-paste lang!**

---

## ✅ PRE-FLIGHT CHECK

Siguraduhin muna na:
- [ ] Naka-save lahat ng files
- [ ] Running ang application locally (test muna)
- [ ] May GitHub account ka na
- [ ] Naka-install ang Git

---

## 📝 STEP 1: Create GitHub Repository

1. **Pumunta sa:** https://github.com/new

2. **Repository settings:**
   - **Repository name:** `elis-stms` (o kahit anong gusto mo)
   - **Description:** `Smart Tenant Management System - The Elis Center`
   - **Visibility:** **Private** (recommended) o Public
   - **⚠️ IMPORTANT:** WAG i-check ang "Add a README file"
   - **⚠️ IMPORTANT:** WAG i-check ang "Add .gitignore"
   - **⚠️ IMPORTANT:** WAG i-check ang "Choose a license"

3. **Click:** "Create repository"

4. **Copy ang Repository URL** (lalabas sa screen):
   ```
   https://github.com/YOUR-USERNAME/elis-stms.git
   ```

---

## 💻 STEP 2: Run These Commands

Open Terminal (iTerm/Terminal app) at pumunta sa project folder:

```bash
cd /Users/regie-302004/Desktop/ElisSystem
```

### Check kung naka-initialize na ang git:
```bash
git status
```

**Kung may error** (walang .git), initialize muna:
```bash
git init
```

### Add all files:
```bash
git add .
```

### Verify what will be committed:
```bash
git status
```

**⚠️ IMPORTANT CHECK:**
- Dapat HINDI kasama ang `.env` file (sensitive data!)
- Dapat HINDI kasama ang `app/static/uploads/` contents
- Dapat HINDI kasama ang `__pycache__/` folders
- Kung nandyan sila, mali ang .gitignore!

### Create first commit:
```bash
git commit -m "Initial commit - ELIS STMS ready for deployment"
```

### Add remote (REPLACE with YOUR actual GitHub URL):
```bash
git remote add origin https://github.com/YOUR-USERNAME/elis-stms.git
```

**Example kung ang username mo ay "regie-302004":**
```bash
git remote add origin https://github.com/regie-302004/elis-stms.git
```

### Rename branch to main:
```bash
git branch -M main
```

### Push to GitHub:
```bash
git push -u origin main
```

**Kung may prompt for username/password:**
- Username: your GitHub username
- Password: use **Personal Access Token** (NOT your GitHub password)

---

## 🔑 STEP 3: Create GitHub Personal Access Token (if needed)

Kung nag-error sa password:

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Note: "ELIS STMS - Git Push"
4. Expiration: 90 days (or longer)
5. Check: ✅ **repo** (full control)
6. Click "Generate token"
7. **COPY THE TOKEN** (makikita mo lang once!)
8. Use this as password when pushing

---

## ✅ STEP 4: Verify on GitHub

1. Open browser
2. Go to: `https://github.com/YOUR-USERNAME/elis-stms`
3. Check if all files are there
4. **⚠️ SECURITY CHECK:**
   - Open `.gitignore` - dapat nandyan
   - Check if `.env` is visible - **DAPAT WALA!**
   - Check if `uploads/` contents visible - **DAPAT WALA!**
   - If nandyan ang .env, **DELETE THE REPO** and start over!

---

## 👥 STEP 5: Add Collaborators (Groupmates)

1. Go to: `https://github.com/YOUR-USERNAME/elis-stms/settings/access`
2. Click "Collaborators"
3. Click "Add people"
4. Enter their GitHub username or email
5. Click "Add [username] to this repository"
6. They'll receive email invitation
7. They click "Accept invitation"

---

## 📊 STEP 6: Repository is Ready!

Your code is now on GitHub! 🎉

**Share with groupmates:**
- **Repository URL:** `https://github.com/YOUR-USERNAME/elis-stms`
- **Clone command:** `git clone https://github.com/YOUR-USERNAME/elis-stms.git`

**Next step:** Deploy to Render! (see `DEPLOY_QUICK_REFERENCE.md`)

---

## 🔄 DAILY GIT COMMANDS (After Initial Push)

### Before starting work:
```bash
git pull origin main
```

### After making changes:
```bash
git add .
git commit -m "Describe what you changed"
git push origin main
```

### Check status anytime:
```bash
git status
```

### View commit history:
```bash
git log --oneline
```

---

## 🆘 Common Issues & Fixes

### Issue: "fatal: not a git repository"
**Fix:**
```bash
git init
```

### Issue: "remote origin already exists"
**Fix:**
```bash
git remote remove origin
git remote add origin https://github.com/YOUR-USERNAME/elis-stms.git
```

### Issue: "Permission denied"
**Fix:** Use Personal Access Token as password (see Step 3)

### Issue: "Updates were rejected"
**Fix:**
```bash
git pull origin main --rebase
git push origin main
```

### Issue: ".env file is visible on GitHub"
**⚠️ CRITICAL FIX:**
1. **DELETE THE REPOSITORY** on GitHub (Settings → Danger Zone → Delete)
2. Remove .env from git:
   ```bash
   git rm --cached .env
   git commit -m "Remove .env from tracking"
   ```
3. Create NEW repository and push again

### Issue: "Large files (uploads/) pushed"
**Fix:**
```bash
git rm -r --cached app/static/uploads/*
git add .gitignore
git commit -m "Remove uploads from tracking"
git push origin main
```

---

## 📋 Verification Checklist

After pushing, verify:

- [ ] Repository visible on GitHub
- [ ] All code files present
- [ ] `.gitignore` file present
- [ ] `.env` file NOT visible (CRITICAL!)
- [ ] `uploads/` contents NOT visible
- [ ] `README.md` displays correctly
- [ ] All documentation files included
- [ ] Collaborators added (if any)
- [ ] Repository visibility correct (Private/Public)

---

## 🎯 What's Next?

After successfully pushing to GitHub:

1. ✅ **Code is safe** - backed up on GitHub
2. ✅ **Team can collaborate** - add collaborators
3. ✅ **Ready to deploy** - proceed to Render deployment

**Next file to read:** `DEPLOY_QUICK_REFERENCE.md`

---

## 💡 Pro Tips

**Good commit messages:**
```bash
✅ "Add payment history feature to tenant dashboard"
✅ "Fix login bug - handle empty email validation"
✅ "Update admin reports to show monthly revenue"
✅ "Improve mobile responsiveness for home page"
```

**Bad commit messages:**
```bash
❌ "update"
❌ "fix"
❌ "changes"
❌ "asdfasdf"
```

**Branch workflow (advanced):**
```bash
# Create feature branch
git checkout -b feature/new-payment-module

# Work on feature
git add .
git commit -m "Add new payment module"

# Push branch
git push origin feature/new-payment-module

# Create Pull Request on GitHub
# After merge, delete branch
git checkout main
git pull origin main
git branch -d feature/new-payment-module
```

---

## 🎉 Success!

Your ELIS STMS code is now on GitHub!

**GitHub Repository:** `https://github.com/YOUR-USERNAME/elis-stms`

Proceed to deployment: `DEPLOY_QUICK_REFERENCE.md`

---

*Push with confidence! Your .gitignore protects sensitive data.* 🔐
