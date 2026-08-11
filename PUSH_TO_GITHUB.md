# 🚀 QUICK GUIDE: PUSH TO GITHUB

## STEP 1: CREATE GITHUB REPOSITORY

1. Go to https://github.com/new
2. Fill in:
   - **Repository name**: `ElisSystem`
   - **Description**: "Smart Tenant Management System for The Elis Center"
   - **Visibility**: Choose **Private** (recommended) or Public
   - **DO NOT** check "Initialize with README"
3. Click "Create repository"

---

## STEP 2: INITIALIZE GIT

Open terminal in your project folder and run:

```bash
cd /Users/regie-302004/Desktop/ElisSystem

# Initialize git
git init

# Add all files
git add .

# Create first commit
git commit -m "Initial commit: STMS ready for deployment"

# Rename branch to main
git branch -M main
```

---

## STEP 3: CONNECT TO GITHUB

**Replace `YOUR_USERNAME` with your GitHub username:**

```bash
git remote add origin https://github.com/YOUR_USERNAME/ElisSystem.git
```

Example:
```bash
git remote add origin https://github.com/john123/ElisSystem.git
```

---

## STEP 4: PUSH TO GITHUB

```bash
git push -u origin main
```

**If asked for username/password:**
- Username: Your GitHub username
- Password: Use **Personal Access Token** (not your password!)

**To create Personal Access Token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Name: "ElisSystem"
4. Select scopes: `repo` (all checkboxes)
5. Click "Generate token"
6. **COPY THE TOKEN** (you won't see it again!)
7. Use this token as password

---

## STEP 5: ADD COLLABORATORS

### 5.1 Invite Team Members

1. Go to your repository on GitHub
2. Click "Settings" tab
3. Click "Collaborators" in sidebar
4. Click "Add people"
5. Enter their GitHub username or email
6. Click "Add [username] to this repository"

### 5.2 They Accept Invitation

1. They check their email
2. Click "View invitation"
3. Click "Accept invitation"
4. Now they can clone and contribute!

---

## ✅ VERIFICATION

**Check if it worked:**

1. Go to `https://github.com/YOUR_USERNAME/ElisSystem`
2. You should see all your files
3. `.env` should **NOT** be there (good!)
4. `README.md` should be visible

---

## 🔄 FUTURE UPDATES

**When you make changes:**

```bash
# Add changed files
git add .

# Commit changes
git commit -m "Your description of changes"

# Push to GitHub
git push origin main
```

---

## 🎉 SUCCESS!

Your code is now on GitHub!

**Share the repo with:**
- Your groupmates (add as collaborators)
- Your professor (share the link)

**Next step:** Deploy to Render.com (see DEPLOYMENT_GUIDE.md)

---

## 🆘 TROUBLESHOOTING

### "Permission denied"
→ Use Personal Access Token instead of password

### "Repository not found"
→ Check if username and repo name are correct

### "Large file" error
→ Check .gitignore includes `.venv/` and other large folders

### "Please tell me who you are"
```bash
git config --global user.email "your-email@gmail.com"
git config --global user.name "Your Name"
```

---

**Need help? Ask in group chat! 💬**
