# 🚀 DEPLOYMENT GUIDE - Render.com

Step-by-step guide to deploy your STMS app to Render.com (FREE tier)

---

## 📋 PRE-DEPLOYMENT CHECKLIST

Before deploying, make sure you have:

- [ ] Supabase database set up and running
- [ ] Gmail SMTP credentials (app password)
- [ ] Google OAuth credentials (optional)
- [ ] GitHub account
- [ ] Render.com account (free)

---

## STEP 1: PREPARE YOUR CODE

### 1.1 Update `.env.example`

Make sure your `.env.example` has all variables (without actual values):

```env
FLASK_ENV=production
SECRET_KEY=change-me-in-production

# Database
DB_TYPE=postgresql
DB_HOST=your-supabase-host
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.your-project-id
DB_PASSWORD=your-password

# Email
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Google OAuth (optional)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-app.onrender.com/auth/google/callback
```

### 1.2 Check required files exist:
- ✅ `.gitignore` (created)
- ✅ `requirements.txt` (created)
- ✅ `runtime.txt` (created)
- ✅ `build.sh` (created)

---

## STEP 2: PUSH TO GITHUB

### 2.1 Initialize Git (if not done)

```bash
cd /Users/regie-302004/Desktop/ElisSystem
git init
```

### 2.2 Add files to Git

```bash
git add .
```

### 2.3 Create initial commit

```bash
git commit -m "Initial commit - STMS ready for deployment"
```

### 2.4 Create GitHub repository

1. Go to https://github.com/new
2. Repository name: `ElisSystem` (or your choice)
3. Description: "Smart Tenant Management System"
4. **IMPORTANT**: Select **Private** if you want to keep it private
5. **DO NOT** initialize with README (we already have one)
6. Click "Create repository"

### 2.5 Push to GitHub

```bash
# Replace YOUR_USERNAME with your GitHub username
git remote add origin https://github.com/YOUR_USERNAME/ElisSystem.git
git branch -M main
git push -u origin main
```

**If you get authentication error:**
- Use Personal Access Token instead of password
- Create token at: https://github.com/settings/tokens

---

## STEP 3: DEPLOY ON RENDER

### 3.1 Create Render Account

1. Go to https://render.com
2. Click "Get Started"
3. Sign up with GitHub account (recommended)
4. Authorize Render to access your repositories

### 3.2 Create New Web Service

1. Click "New +" button (top right)
2. Select "Web Service"
3. Click "Connect a repository"
4. If private repo: Grant Render access to your repository
5. Find and select "ElisSystem"
6. Click "Connect"

### 3.3 Configure Web Service

**Basic Settings:**
- **Name**: `elis-stms` (or your choice)
  - This will be your URL: `elis-stms.onrender.com`
- **Region**: Singapore (closest to Philippines)
- **Branch**: `main`
- **Runtime**: `Python 3`

**Build & Deploy:**
- **Build Command**: `./build.sh`
- **Start Command**: `gunicorn run:app`

**Instance Type:**
- Select **Free** (perfect for testing)

### 3.4 Add Environment Variables

Click "Advanced" → "Add Environment Variable"

**Add these variables ONE BY ONE:**

```
FLASK_ENV = production

SECRET_KEY = [generate new random string]

DB_TYPE = postgresql

DB_HOST = aws-0-ap-southeast-1.pooler.supabase.com

DB_PORT = 5432

DB_NAME = postgres

DB_USER = postgres.qthrznudzkgzrwvygmbd

DB_PASSWORD = Elis2026#123

UPLOAD_FOLDER = app/static/uploads

MAX_CONTENT_LENGTH_MB = 10

MAIL_SERVER = smtp.gmail.com

MAIL_PORT = 587

MAIL_USE_TLS = 1

MAIL_USE_SSL = 0

MAIL_USERNAME = elis.stms.otp@gmail.com

MAIL_PASSWORD = vbvvytuxfcflbtkr

MAIL_DEFAULT_SENDER = STMS <elis.stms.otp@gmail.com>

RESERVATION_AUTO_CANCEL_HOURS = 48

GOOGLE_CLIENT_ID = 458095561145-rofv0i806rdsqru6m3dcbhd37i5jjh7p.apps.googleusercontent.com

GOOGLE_CLIENT_SECRET = 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

GOOGLE_REDIRECT_URI = https://elis-stms.onrender.com/auth/google/callback
```

**IMPORTANT:**
- Replace `elis-stms` in `GOOGLE_REDIRECT_URI` with YOUR app name
- Generate new `SECRET_KEY` for production (use random string generator)

### 3.5 Deploy!

1. Click "Create Web Service"
2. Render will start building your app
3. Wait 5-10 minutes for first deployment
4. Watch the logs for any errors

---

## STEP 4: UPDATE GOOGLE OAUTH (IF USING)

### 4.1 Add Render URL to Google Cloud Console

1. Go to https://console.cloud.google.com
2. Select your project
3. Go to "APIs & Services" → "Credentials"
4. Click on your OAuth 2.0 Client ID
5. Under "Authorized redirect URIs", add:
   ```
   https://elis-stms.onrender.com/auth/google/callback
   ```
   (Replace `elis-stms` with your app name)
6. Click "Save"

---

## STEP 5: TEST YOUR DEPLOYMENT

### 5.1 Access your app

```
https://elis-stms.onrender.com
```

### 5.2 Test admin login

- Email: `admin@gmail.com`
- Password: `admin123`

### 5.3 Test features:
- [ ] Login works
- [ ] Google OAuth works (if configured)
- [ ] Dashboard loads
- [ ] Database connection works
- [ ] Email sending works (try registration)
- [ ] File uploads work

---

## ⚠️ IMPORTANT NOTES

### Free Tier Limitations:
- **Spins down after 15 minutes** of inactivity
- First request after sleep takes **30-60 seconds** to wake up
- **512 MB RAM** limit
- **Good for**: Testing, demo, portfolio

### Upgrade when:
- Getting regular users
- Need faster response times
- **Cost**: $7/month for Starter plan (always-on)

---

## 🔧 TROUBLESHOOTING

### Build fails:
- Check `build.sh` has execute permissions
- Check `requirements.txt` has all dependencies
- Check Python version in `runtime.txt` is supported

### App crashes on start:
- Check environment variables are set correctly
- Check database connection string
- View logs in Render dashboard

### Database connection fails:
- Make sure using **Session Pooler** host (IPv4)
- Check Supabase is accessible
- Verify credentials

### Uploads don't persist:
- **Render Free tier doesn't persist uploads!**
- Files disappear after spin-down/restart
- Solution: Use cloud storage (Cloudinary, AWS S3)
- Or: Upgrade to paid plan with persistent disk

---

## 📊 MONITORING

### View logs:
1. Go to Render dashboard
2. Select your service
3. Click "Logs" tab
4. Real-time logs appear here

### Check metrics:
- CPU usage
- Memory usage
- Request volume
- Response times

---

## 🔄 UPDATING YOUR APP

### After making changes:

```bash
git add .
git commit -m "Your change description"
git push origin main
```

**Render will automatically:**
- Detect the push
- Rebuild your app
- Deploy the new version

**Auto-deploy is enabled by default!**

---

## 🎉 SUCCESS!

Your STMS app is now live on the internet!

**Share with:**
- Your groupmates
- Your professor
- Your friends
- On your portfolio

**Next steps:**
- Add custom domain (optional)
- Set up monitoring/alerts
- Upgrade to paid plan when ready
- Add more features!

---

## 📞 SUPPORT

**Issues?**
- Check Render logs first
- Review this guide
- Ask your groupmates
- Google the error message

**Resources:**
- Render Docs: https://render.com/docs
- Flask Docs: https://flask.palletsprojects.com
- Supabase Docs: https://supabase.com/docs

---

**Good luck with your deployment! 🚀**
