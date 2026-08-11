# 🚀 Quick Deploy Reference - ELIS STMS

## Step-by-Step Commands (Copy-Paste Ready)

### 1️⃣ PUSH TO GITHUB

```bash
# Go to project directory
cd /Users/regie-302004/Desktop/ElisSystem

# Initialize git (if needed)
git init

# Add all files
git add .

# First commit
git commit -m "Initial commit - ELIS STMS ready for deployment"

# Add remote (REPLACE with your actual GitHub URL)
git remote add origin https://github.com/YOUR-USERNAME/elis-stms.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**After pushing, GitHub URL will be:** `https://github.com/YOUR-USERNAME/elis-stms`

---

### 2️⃣ DEPLOY TO RENDER

#### A. Create Account
1. Go to: https://render.com
2. Sign up with GitHub (recommended)

#### B. Create Web Service
1. Click "New +" → "Web Service"
2. Connect your repository: `elis-stms`
3. Configure:
   - **Name:** `elis-stms`
   - **Region:** Singapore (or closest)
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -k eventlet -w 1 --bind 0.0.0.0:$PORT run:app`
   - **Instance Type:** Free (or Starter for production)

#### C. Add Environment Variables

Copy-paste these (update values):

```
FLASK_ENV=production
SECRET_KEY=<run command below to generate>
DB_TYPE=postgresql
DB_HOST=aws-0-ap-southeast-1.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.qthrznudzkgzrwvygmbd
DB_PASSWORD=Elis2026#123
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=STMS <no-reply@elis.local>
UPLOAD_FOLDER=app/static/uploads
MAX_CONTENT_LENGTH_MB=10
RESERVATION_AUTO_CANCEL_HOURS=48
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

**Generate SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### D. Deploy
1. Click "Create Web Service"
2. Wait 5-10 minutes
3. Your URL: `https://elis-stms.onrender.com`

---

### 3️⃣ UPDATE GOOGLE OAUTH

After deployment, update redirect URIs:

1. Go to: https://console.cloud.google.com
2. Select project → APIs & Services → Credentials
3. Click your OAuth Client ID
4. Add to **Authorized redirect URIs:**
   ```
   https://elis-stms.onrender.com/auth/google/callback
   ```
5. Add to **Authorized JavaScript origins:**
   ```
   https://elis-stms.onrender.com
   ```
6. Save

---

### 4️⃣ TEST DEPLOYMENT

Open your Render URL and test:
- ✅ Homepage loads
- ✅ Login/Register works
- ✅ Google OAuth works
- ✅ Email OTP works
- ✅ Admin dashboard accessible
- ✅ Database connected

---

### 5️⃣ INVITE GROUPMATES

#### On GitHub:
1. Go to repository → Settings → Collaborators
2. Click "Add people"
3. Enter username/email
4. They accept invitation via email

#### Groupmates Clone & Setup:
```bash
# Clone
git clone https://github.com/YOUR-USERNAME/elis-stms.git
cd elis-stms

# Virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows

# Install
pip install -r requirements.txt

# Setup .env
cp .env.example .env
# Edit .env with credentials (ask repository owner)

# Run locally
python run.py
```

---

## 📊 Daily Workflow for Team

### Before Starting Work:
```bash
git pull origin main
```

### After Making Changes:
```bash
git add .
git commit -m "Descriptive message about changes"
git push origin main
```

Render auto-deploys when you push to main! 🎉

---

## 🔥 Important URLs

- **GitHub Repo:** `https://github.com/YOUR-USERNAME/elis-stms`
- **Render Dashboard:** `https://dashboard.render.com`
- **Supabase Dashboard:** `https://supabase.com/dashboard`
- **Google Console:** `https://console.cloud.google.com`
- **Live App:** `https://elis-stms.onrender.com`

---

## 🆘 Common Issues

### Build Failed on Render
- Check requirements.txt format
- Check Python version in runtime.txt (3.12.6)
- View logs in Render dashboard

### Database Connection Error
- Verify Supabase credentials in Render environment variables
- Check if Supabase project is active
- Verify connection pooler URL

### Google OAuth Error
- Verify redirect URIs include Render URL
- Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in Render

### Email Not Sending
- Verify Gmail App Password (not regular password)
- Check MAIL_USERNAME and MAIL_PASSWORD in Render
- Enable 2FA on Gmail and create App Password

---

## 📞 Resources

- **Detailed GitHub Guide:** `GITHUB_SETUP.md`
- **Detailed Render Guide:** `DEPLOYMENT_RENDER.md`
- **Environment Example:** `.env.example`
- **Render Config:** `render.yaml`

---

## ✅ Deployment Checklist

**Before Deployment:**
- [ ] Code working locally
- [ ] Supabase database set up
- [ ] Gmail App Password created
- [ ] Google OAuth credentials ready
- [ ] All sensitive data in .env

**GitHub:**
- [ ] Repository created
- [ ] Code pushed to main branch
- [ ] Collaborators added

**Render:**
- [ ] Account created
- [ ] Web service connected to GitHub
- [ ] All environment variables added
- [ ] Service deployed successfully
- [ ] Live URL accessible

**Post-Deployment:**
- [ ] Google OAuth redirect URIs updated
- [ ] Login/register tested
- [ ] Admin dashboard accessible
- [ ] Database operations working
- [ ] Email notifications working

---

## 🎉 Done!

Your ELIS STMS is now live and your team can collaborate!

**Next Steps:**
1. Share GitHub repo URL with groupmates
2. Share Render live URL for testing
3. Monitor logs for issues
4. Regular backups of Supabase database
5. Update Google OAuth for production domain

---

*Deploy with confidence! 💪*
