# 👥 TEAM COLLABORATION GUIDE

Guide for groupmates to collaborate on the STMS project using GitHub

---

## 🎯 QUICK START FOR TEAM MEMBERS

### Prerequisites
- Git installed on your computer
- GitHub account
- Python 3.11+ installed
- Access to the GitHub repository

---

## STEP 1: CLONE THE REPOSITORY

### First Time Setup

1. **Get repository access**
   - Ask the repo owner to add you as a collaborator
   - Check your email for GitHub invitation
   - Accept the invitation

2. **Clone the repository**
```bash
# Navigate to where you want the project
cd ~/Desktop

# Clone the repository (replace YOUR_USERNAME)
git clone https://github.com/YOUR_USERNAME/ElisSystem.git

# Enter the project folder
cd ElisSystem
```

---

## STEP 2: SET UP LOCAL ENVIRONMENT

### 2.1 Create Virtual Environment

**On macOS/Linux:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

**On Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2.2 Install Dependencies

```bash
pip install -r requirements.txt
```

### 2.3 Set Up Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your text editor
# Ask team lead for the actual credentials
```

**Get credentials from team lead:**
- Supabase database credentials
- Gmail SMTP credentials
- Google OAuth credentials

### 2.4 Test the App

```bash
python3.11 run.py
```

Open browser: `http://127.0.0.1:5001`

---

## STEP 3: WORKFLOW - MAKING CHANGES

### 3.1 Always Start by Pulling Latest Changes

```bash
# Make sure you're on main branch
git checkout main

# Get latest changes from GitHub
git pull origin main
```

### 3.2 Create a New Branch for Your Feature

```bash
# Create and switch to new branch
git checkout -b feature/your-feature-name

# Examples:
git checkout -b feature/add-payment-page
git checkout -b fix/login-bug
git checkout -b update/improve-dashboard
```

**Branch Naming Convention:**
- `feature/` - New features
- `fix/` - Bug fixes
- `update/` - Improvements to existing features
- `docs/` - Documentation changes

### 3.3 Make Your Changes

- Edit files in your code editor
- Test your changes locally
- Make sure app still runs

### 3.4 Commit Your Changes

```bash
# See what files you changed
git status

# Add files to commit
git add .

# Or add specific files
git add app/templates/admin/payments.html
git add app/blueprints/admin/routes.py

# Commit with descriptive message
git commit -m "Add: payment history page for admin"
```

**Good Commit Messages:**
```
✅ Add: payment history page for admin
✅ Fix: login redirect bug
✅ Update: improve dashboard chart colors
✅ Remove: unused imports in models.py
```

**Bad Commit Messages:**
```
❌ update
❌ changes
❌ fixed stuff
❌ asdf
```

### 3.5 Push to GitHub

```bash
# Push your branch to GitHub
git push origin feature/your-feature-name
```

### 3.6 Create Pull Request

1. Go to GitHub repository
2. You'll see "Compare & pull request" button
3. Click it
4. Fill in details:
   - **Title**: Brief description
   - **Description**: What changes you made and why
   - **Screenshots**: Add if relevant
5. Request review from team members
6. Click "Create pull request"

### 3.7 Wait for Review

- Team members will review your code
- They might suggest changes
- Make requested changes if needed
- Push again (same branch)

### 3.8 Merge

- Once approved, click "Merge pull request"
- Delete your feature branch (optional)

---

## STEP 4: KEEPING YOUR BRANCH UPDATED

If you're working on a long feature and main branch has new updates:

```bash
# While on your feature branch
git checkout feature/your-feature-name

# Get latest from main
git fetch origin main
git merge origin/main

# Resolve conflicts if any
# Push updated branch
git push origin feature/your-feature-name
```

---

## 🚨 COMMON SCENARIOS

### Someone Else Changed the Same File

**Merge Conflict!**

```bash
# Git will tell you which files have conflicts
# Open the file, you'll see:

<<<<<<< HEAD
Your changes
=======
Their changes
>>>>>>> main

# Choose which to keep or combine both
# Remove the conflict markers
# Save file

# Mark as resolved
git add conflicted-file.py

# Continue merge
git commit -m "Merge: resolve conflicts"

# Push
git push origin your-branch-name
```

### I Made Changes on Main Instead of Feature Branch

```bash
# Create new branch with your current changes
git checkout -b feature/my-feature

# Your changes are now on the new branch!
# Push it
git push origin feature/my-feature
```

### I Want to Undo My Last Commit

```bash
# Undo last commit but keep changes
git reset --soft HEAD~1

# Undo last commit and discard changes
git reset --hard HEAD~1
```

### I Want to See What Changed

```bash
# See uncommitted changes
git diff

# See changes in specific file
git diff app/models.py

# See commit history
git log --oneline
```

---

## 📋 TEAM WORKFLOW

### Daily Workflow

1. **Morning**: Pull latest changes
```bash
git checkout main
git pull origin main
```

2. **Create feature branch**
```bash
git checkout -b feature/todays-task
```

3. **Work on your task**
   - Code
   - Test
   - Commit frequently

4. **End of day**: Push your work
```bash
git push origin feature/todays-task
```

5. **Create PR when ready**
   - Let team review
   - Merge when approved

### Communication

**Before starting work:**
- Announce in group chat what you're working on
- Check if anyone else is working on same files
- Avoid conflicts!

**When stuck:**
- Ask in group chat
- Create issue on GitHub
- Review existing PRs for ideas

---

## 🎨 CODE STYLE GUIDE

### Python (Backend)
```python
# Use snake_case for variables and functions
user_name = "John"
def get_user_profile():
    pass

# Use PascalCase for classes
class UserProfile:
    pass

# Add docstrings
def calculate_rent(unit_price, months):
    """
    Calculate total rent for specified months.
    
    Args:
        unit_price (float): Monthly rent price
        months (int): Number of months
    
    Returns:
        float: Total rent amount
    """
    return unit_price * months
```

### HTML/Jinja2 (Frontend)
```html
<!-- Use 2-space indentation -->
<div class="card">
  <h3 class="card__title">{{ title }}</h3>
  <p class="card__text">{{ description }}</p>
</div>

<!-- Use BEM naming for classes -->
<!-- Block__Element--Modifier -->
<button class="btn btn--primary btn--large">
  Submit
</button>
```

### JavaScript
```javascript
// Use camelCase
const userName = 'John';
function getUserProfile() {
  // code
}

// Use const/let, not var
const API_URL = '/api/users';
let userCount = 0;

// Add comments for complex logic
// Calculate total rent including deposits
const totalAmount = monthlyRent * months + securityDeposit;
```

---

## 🧪 TESTING YOUR CHANGES

### Before Committing:

- [ ] App runs without errors
- [ ] Your feature works as expected
- [ ] Didn't break existing features
- [ ] No console errors
- [ ] Tested on different browsers (if frontend)
- [ ] Code follows team style guide

### Test Different Roles:

- [ ] Admin view
- [ ] Tenant view
- [ ] User view
- [ ] Not logged in view

---

## 📁 FILE ORGANIZATION

### Where to Add/Edit Files:

**Backend routes:**
- `app/blueprints/admin/routes.py` - Admin pages
- `app/blueprints/tenant/routes.py` - Tenant pages
- `app/blueprints/auth/routes.py` - Login/register
- `app/blueprints/api/routes.py` - API endpoints

**Frontend templates:**
- `app/templates/admin/` - Admin pages
- `app/templates/tenant/` - Tenant pages
- `app/templates/auth/` - Login/register pages
- `app/templates/components/` - Reusable components

**Static files:**
- `app/static/css/` - Stylesheets
- `app/static/js/` - JavaScript files
- `app/static/img/` - Images

**Database:**
- `app/models.py` - Database models

---

## 🚫 DON'T DO THIS

### Never commit:
- ❌ `.env` file (has passwords!)
- ❌ `.venv/` folder (too large)
- ❌ `__pycache__/` folders
- ❌ `.DS_Store` files
- ❌ Personal test files
- ❌ Uploaded images (unless necessary)

### Never push directly to main:
- ❌ Always use feature branches
- ❌ Always create PR
- ❌ Always get review

### Don't:
- ❌ Commit broken code
- ❌ Commit commented-out code
- ❌ Commit "test" or "asdf" messages
- ❌ Work on main branch
- ❌ Force push (`git push -f`) unless you know what you're doing

---

## 💡 TIPS FOR SUCCESS

### Git Tips:
- Commit often (small commits are better)
- Write clear commit messages
- Pull before starting work
- Test before pushing
- Review your own changes before PR

### Team Tips:
- Communicate what you're working on
- Help review others' PRs
- Ask questions when stuck
- Share your knowledge
- Be patient with merge conflicts

### Code Tips:
- Follow the existing code style
- Add comments for complex logic
- Don't repeat code (use functions)
- Keep functions small and focused
- Test your changes

---

## 📞 GET HELP

**Git Issues:**
- Google the error message
- Ask in team chat
- Check GitHub guides: https://guides.github.com

**Code Issues:**
- Read error messages carefully
- Check Flask docs: https://flask.palletsprojects.com
- Ask team members
- Review similar code in project

**Database Issues:**
- Check Supabase dashboard
- Verify connection string
- Ask for fresh `.env` file

---

## 🎉 YOU'RE READY!

**Next steps:**
1. Clone the repository
2. Set up your environment
3. Pick a task from issues/project board
4. Create a branch
5. Start coding!

**Remember:**
- Pull before work
- Branch for features
- Commit often
- Push regularly
- Create PRs
- Help review

**Happy coding! 🚀**

---

## 📚 ADDITIONAL RESOURCES

- Git Cheat Sheet: https://education.github.com/git-cheat-sheet-education.pdf
- Flask Tutorial: https://flask.palletsprojects.com/tutorial/
- Python Style Guide (PEP 8): https://pep8.org/
- GitHub Flow: https://guides.github.com/introduction/flow/
