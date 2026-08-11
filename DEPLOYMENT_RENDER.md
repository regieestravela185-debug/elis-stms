# 🚀 Render Deployment Guide - ELIS STMS

Complete step-by-step guide to deploy your Smart Tenant Management System to Render.

---

## 📋 Pre-Deployment Checklist

✅ Supabase PostgreSQL database is set up and running
✅ Google OAuth credentials configured (if using)
✅ Gmail App Password for email notifications (if using)
✅ All environment variables ready
✅ Code pushed to GitHub repository

---

## 🔧 Step 1: Prepare Your GitHub Repository

### 1.1 Initialize Git (if not already done)
```bash
cd /Users/regie-302004/Desktop/ElisSystem
git init
git add .
git commit -m "Initial commit - ELIS STMS ready for deployment"
```

### 1.2 Create GitHub Repository
1. Go to https://github.com/new
2. Repository name: `elis-stms` (or your preferred name)
3. Description: "Smart Tenant Management System with Flask and Supabase"
4. Choose: **Private** (recommended for production apps)
5. **DO NOT** initialize with README (you already have one)
6. Click "Create repository"

### 1.3 Push to GitHub
```bash
# Replace YOUR-USERNAME and YOUR-REPO with your actual values
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git branch -M main
git push -u origin main
```

---

## 🌐 Step 2: Deploy to Render

### 2.1 Sign Up / Login to Render
1. Go to https://render.com
2. Sign up or login (you can use GitHub authentication)
3. Click "New +" button in dashboard

### 2.2 Create Web Service
1. Click **"New Web Service"**
2. Choose **"Build and deploy from a Git repository"**
3. Click **"Connect account"** to link your GitHub
4. Select your repository: `elis-stms`
5. Click **"Connect"**

### 2.3 Configure Service Settings

**Basic Settings:**
- **Name:** `elis-stms` (or your preferred name)
- **Region:** Choose closest to your users (e.g., Singapore, Oregon)
- **Branch:** `main`
- **Root Directory:** leave blank
- **Environment:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn -k eventlet -w 1 --bind 0.0.0.0:$PORT run:app`

**Instance Type:**
- Choose **Free** tier for testing (sleeps after 15 mins of inactivity)
- Or upgrade to **Starter** ($7/month) for production (no sleep)

### 2.4 Add Environment Variables

Click **"Advanced"** then add these environment variables:

#### Required Database Variables
```
DB_TYPE=postgresql
DB_HOST=aws-0-ap-southeast-1.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.qthrznudzkgzrwvygmbd
DB_PASSWORD=Elis2026#123
```

#### Required Flask Variables
```
FLASK_ENV=production
SECRET_KEY=<generate-random-32-character-string>
```

**Generate SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### Email Variables (for OTP)
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=STMS <no-reply@elis.local>
```

#### Google OAuth Variables (if using)
```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

#### Other Variables
```
UPLOAD_FOLDER=app/static/uploads
MAX_CONTENT_LENGTH_MB=10
RESERVATION_AUTO_CANCEL_HOURS=48
```

### 2.5 Create Service
1. Review all settings
2. Click **"Create Web Service"**
3. Wait for deployment (5-10 minutes)
4. Watch the build logs for any errors

---

## 🔐 Step 3: Update Google OAuth Redirect URIs

### 3.1 Get Your Render URL
After deployment completes, you'll get a URL like:
```
https://elis-stms.onrender.com
```

### 3.2 Update Google Cloud Console
1. Go to https://console.cloud.google.com
2. Select your project
3. Go to **APIs & Services** > **Credentials**
4. Click on your OAuth 2.0 Client ID
5. Add to **Authorized redirect URIs:**
   ```
   https://elis-stms.onrender.com/auth/google/callback
   ```
6. Add to **Authorized JavaScript origins:**
   ```
   https://elis-stms.onrender.com
   ```
7. Click **Save**

---

## ✅ Step 4: Verify Deployment

### 4.1 Test Your Application
1. Open your Render URL: `https://your-app.onrender.com`
2. Test login functionality
3. Test Google OAuth sign-in
4. Test email OTP verification
5. Test admin dashboard access
6. Test tenant registration

### 4.2 Check Logs
If something doesn't work:
1. Go to Render Dashboard
2. Click on your service
3. Click **"Logs"** tab
4. Check for error messages

---

## 🔄 Step 5: Continuous Deployment

### 5.1 Auto-Deploy on Git Push
Render automatically deploys when you push to main branch:

```bash
# Make changes to your code
git add .
git commit -m "Update feature"
git push origin main
# Render will automatically rebuild and deploy
```

### 5.2 Manual Deploy
1. Go to Render Dashboard
2. Click on your service
3. Click **"Manual Deploy"** > **"Deploy latest commit"**

---

## 👥 Step 6: Collaborate with Groupmates

### 6.1 Add Collaborators to GitHub
1. Go to your GitHub repository
2. Click **Settings** > **Collaborators**
3. Click **"Add people"**
4. Enter their GitHub username or email
5. They'll receive an invitation

### 6.2 Collaborator Workflow
Your groupmates can now:

```bash
# Clone the repository
git clone https://github.com/YOUR-USERNAME/elis-stms.git
cd elis-stms

# Create virtual environment (Python 3.12.6)
python3.12 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file (copy from .env.example)
cp .env.example .env
# Then edit .env with actual credentials

# Run locally
python3.12 run.py
```

### 6.3 Development Workflow
```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes and commit
git add .
git commit -m "Add new feature"

# Push branch
git push origin feature/new-feature

# Create Pull Request on GitHub
# After review, merge to main
# Render auto-deploys merged changes
```

---

## 🛠️ Troubleshooting

### Issue: Build Fails
**Solution:** Check `requirements.txt` dependencies match Python 3.12.6

### Issue: Database Connection Error
**Solution:** Verify Supabase connection string and credentials in environment variables

### Issue: Service Crashes on Startup
**Solution:** 
- Check logs for specific error
- Verify `gunicorn` command syntax
- Ensure `run.py` exists and imports `app` correctly

### Issue: Google OAuth Redirect Mismatch
**Solution:** Make sure Render URL is added to Google Console redirect URIs

### Issue: File Uploads Not Working
**Solution:** Render uses ephemeral storage. Consider using cloud storage (AWS S3, Cloudinary) for production

### Issue: Free Tier Service Sleeps
**Solution:** 
- Upgrade to Starter plan ($7/month)
- Or use a cron job to ping your service every 10 minutes

---

## 📊 Monitoring & Maintenance

### View Logs
```
Render Dashboard > Your Service > Logs
```

### Restart Service
```
Render Dashboard > Your Service > Manual Deploy > Clear build cache & deploy
```

### Environment Variables
```
Render Dashboard > Your Service > Environment > Add/Edit variables
```

### Database Backups
Use Supabase built-in backup system:
```
Supabase Dashboard > Your Project > Database > Backups
```

---

## 🎉 Success!

Your ELIS Smart Tenant Management System is now live on Render!

**Next Steps:**
- Share URL with your groupmates
- Set up custom domain (optional)
- Monitor usage and performance
- Regular database backups
- Security audits

---

## 📞 Support

**Render Documentation:** https://render.com/docs
**Supabase Documentation:** https://supabase.com/docs
**Flask Documentation:** https://flask.palletsprojects.com/

---

*Last Updated: August 11, 2026*
