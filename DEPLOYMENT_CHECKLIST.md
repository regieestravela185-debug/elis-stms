# ✅ Deployment Checklist - ELIS STMS

Use this checklist to make sure everything is ready before and after deployment.

---

## 🔧 PRE-DEPLOYMENT CHECKLIST

### Local Development
- [ ] Application runs successfully locally (`python run.py`)
- [ ] All features tested and working
- [ ] No critical bugs or errors
- [ ] Database migrations completed
- [ ] All dependencies in `requirements.txt`
- [ ] `.env` file configured and working
- [ ] Virtual environment using Python 3.12.6

### Database (Supabase)
- [ ] Supabase project created
- [ ] PostgreSQL schema imported (`stms_elis_postgresql_FULL.sql`)
- [ ] Session Pooler connection string obtained
- [ ] Database password saved securely
- [ ] Admin user exists in database
- [ ] Sample buildings added (if needed)
- [ ] Connection tested successfully

### Email Configuration (Gmail)
- [ ] Gmail account available
- [ ] 2-Factor Authentication enabled on Gmail
- [ ] App Password generated (16 characters)
- [ ] Email sending tested locally
- [ ] MAIL_USERNAME configured
- [ ] MAIL_PASSWORD (App Password) configured

### Google OAuth (Optional)
- [ ] Google Cloud Project created
- [ ] OAuth 2.0 Client ID created
- [ ] Client ID and Secret obtained
- [ ] Local redirect URI configured (`http://localhost:5000/auth/google/callback`)
- [ ] Google OAuth tested locally
- [ ] Consent screen configured

### Code & Files
- [ ] `.gitignore` updated (excludes .env, uploads, __pycache__)
- [ ] `.env.example` updated with all required variables
- [ ] `requirements.txt` includes all dependencies
- [ ] `runtime.txt` specifies Python 3.12.6
- [ ] `render.yaml` configuration created
- [ ] README.md updated
- [ ] Documentation files created
- [ ] No sensitive data in code (passwords, keys)

---

## 🐙 GITHUB SETUP CHECKLIST

### Repository Creation
- [ ] GitHub account created/logged in
- [ ] New repository created (`elis-stms`)
- [ ] Repository visibility set (Private/Public)
- [ ] Repository description added

### Push Code
- [ ] Git initialized (`git init`)
- [ ] Files staged (`git add .`)
- [ ] Initial commit created (`git commit -m "..."`)
- [ ] Remote origin added (`git remote add origin ...`)
- [ ] Code pushed to main branch (`git push -u origin main`)
- [ ] All files visible on GitHub
- [ ] `.env` file NOT visible on GitHub (check!)

### Collaborators
- [ ] Groupmates added as collaborators
- [ ] Invitations sent via email
- [ ] Collaborators accepted invitations
- [ ] Collaborators can see repository

### Documentation
- [ ] README.md displays correctly on GitHub
- [ ] All documentation files included
- [ ] Links in README work
- [ ] Project description clear

---

## 🚀 RENDER DEPLOYMENT CHECKLIST

### Account Setup
- [ ] Render account created (https://render.com)
- [ ] Email verified
- [ ] GitHub connected to Render

### Web Service Creation
- [ ] "New Web Service" created
- [ ] GitHub repository connected
- [ ] Correct repository selected
- [ ] Service name set (`elis-stms`)
- [ ] Region selected (closest to users)
- [ ] Branch set to `main`

### Build Configuration
- [ ] Environment: Python 3
- [ ] Build Command: `pip install -r requirements.txt`
- [ ] Start Command: `gunicorn -k eventlet -w 1 --bind 0.0.0.0:$PORT run:app`
- [ ] Instance Type selected (Free/Starter)

### Environment Variables
All variables added in Render dashboard:

**Database (Required):**
- [ ] `DB_TYPE` = postgresql
- [ ] `DB_HOST` = aws-0-ap-southeast-1.pooler.supabase.com
- [ ] `DB_PORT` = 5432
- [ ] `DB_NAME` = postgres
- [ ] `DB_USER` = postgres.qthrznudzkgzrwvygmbd
- [ ] `DB_PASSWORD` = Elis2026#123

**Flask (Required):**
- [ ] `FLASK_ENV` = production
- [ ] `SECRET_KEY` = (generated 64-char random string)

**Email (Required for OTP):**
- [ ] `MAIL_SERVER` = smtp.gmail.com
- [ ] `MAIL_PORT` = 587
- [ ] `MAIL_USE_TLS` = 1
- [ ] `MAIL_USERNAME` = your-email@gmail.com
- [ ] `MAIL_PASSWORD` = your-gmail-app-password
- [ ] `MAIL_DEFAULT_SENDER` = STMS <no-reply@elis.local>

**Google OAuth (Optional):**
- [ ] `GOOGLE_CLIENT_ID` = your-client-id.apps.googleusercontent.com
- [ ] `GOOGLE_CLIENT_SECRET` = your-client-secret

**Other Settings:**
- [ ] `UPLOAD_FOLDER` = app/static/uploads
- [ ] `MAX_CONTENT_LENGTH_MB` = 10
- [ ] `RESERVATION_AUTO_CANCEL_HOURS` = 48

### Deployment
- [ ] "Create Web Service" clicked
- [ ] Build started successfully
- [ ] Build completed without errors (check logs)
- [ ] Service status: "Live"
- [ ] Render URL obtained (e.g., https://elis-stms.onrender.com)

---

## 🔐 POST-DEPLOYMENT CHECKLIST

### Google OAuth Update
- [ ] Render URL copied
- [ ] Google Cloud Console opened
- [ ] OAuth Client ID settings accessed
- [ ] Production redirect URI added:
  - `https://elis-stms.onrender.com/auth/google/callback`
- [ ] Production origin added:
  - `https://elis-stms.onrender.com`
- [ ] Changes saved in Google Console

### Application Testing
- [ ] Homepage loads successfully
- [ ] CSS and JavaScript load correctly
- [ ] Images display properly
- [ ] No console errors (check browser DevTools)

### Authentication Testing
- [ ] Login page accessible
- [ ] Register page accessible
- [ ] Email/password login works
- [ ] Email/password registration works
- [ ] OTP email received
- [ ] OTP verification works
- [ ] Google OAuth button displays
- [ ] Google OAuth login works
- [ ] Google OAuth account selection appears
- [ ] Logout works

### Role-Based Access
- [ ] Admin login successful
- [ ] Admin dashboard accessible
- [ ] Admin features work
- [ ] Tenant registration works
- [ ] Tenant login successful
- [ ] Tenant dashboard accessible
- [ ] Tenant features work
- [ ] User (non-tenant) access works

### Database Operations
- [ ] User registration saves to database
- [ ] Login updates last_login_at
- [ ] Data retrieval works (buildings, units)
- [ ] Data creation works (new tenant)
- [ ] Data update works (edit profile)
- [ ] Data deletion works (if applicable)
- [ ] Database connection stable

### Email Functionality
- [ ] OTP emails sent successfully
- [ ] Password reset emails sent
- [ ] Email formatting correct
- [ ] Links in emails work
- [ ] Sender name displays correctly

### Real-Time Features
- [ ] WebSocket connection established
- [ ] Live notifications work
- [ ] Real-time updates display
- [ ] Socket.IO connects successfully

### Performance
- [ ] Page load times acceptable (<3 seconds)
- [ ] Database queries fast
- [ ] No timeout errors
- [ ] Images load quickly
- [ ] No memory issues

### Error Handling
- [ ] 404 page works
- [ ] 500 errors handled gracefully
- [ ] Flash messages display correctly
- [ ] Form validation works
- [ ] Error logs accessible in Render

---

## 👥 TEAM COLLABORATION CHECKLIST

### Collaborators Setup
- [ ] All groupmates have GitHub accounts
- [ ] All invited as collaborators
- [ ] All accepted invitations
- [ ] All can access repository

### Local Development Setup (Each Member)
- [ ] Repository cloned
- [ ] Python 3.12.6 installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` file created
- [ ] Credentials obtained from owner
- [ ] Application runs locally
- [ ] Can pull from GitHub
- [ ] Can push to GitHub

### Workflow Agreement
- [ ] Git workflow discussed
- [ ] Branch naming convention agreed
- [ ] Commit message format agreed
- [ ] Pull request process defined
- [ ] Code review process established
- [ ] Communication channel set up

---

## 📊 MONITORING CHECKLIST

### Daily Monitoring
- [ ] Check Render logs for errors
- [ ] Monitor application uptime
- [ ] Check database usage
- [ ] Review user registrations
- [ ] Monitor email sending success

### Weekly Tasks
- [ ] Review Render analytics
- [ ] Check Supabase storage usage
- [ ] Review database backups
- [ ] Update dependencies if needed
- [ ] Check for security updates

### Monthly Tasks
- [ ] Review application performance
- [ ] Analyze user activity
- [ ] Plan new features
- [ ] Database optimization
- [ ] Security audit

---

## 🆘 TROUBLESHOOTING CHECKLIST

If something doesn't work:

### Check Render Logs
- [ ] Accessed Render dashboard
- [ ] Viewed "Logs" tab
- [ ] Identified error messages
- [ ] Noted timestamps

### Verify Environment Variables
- [ ] All variables present in Render
- [ ] No typos in variable names
- [ ] Values are correct (no quotes)
- [ ] Sensitive values not exposed

### Database Connection
- [ ] Supabase project active
- [ ] Connection string correct
- [ ] Database credentials valid
- [ ] Network allows connection
- [ ] Session pooler URL used

### Google OAuth
- [ ] Redirect URIs match exactly
- [ ] No trailing slashes
- [ ] HTTPS used (not HTTP)
- [ ] Client ID/Secret correct

### Email Issues
- [ ] Gmail App Password used (not regular password)
- [ ] 2FA enabled on Gmail
- [ ] MAIL_USERNAME is email address
- [ ] SMTP settings correct

---

## ✅ FINAL VERIFICATION

Before announcing deployment success:

- [ ] Application accessible via Render URL
- [ ] All core features tested and working
- [ ] No critical bugs
- [ ] Documentation complete
- [ ] Team can access and contribute
- [ ] Monitoring set up
- [ ] Backup strategy in place
- [ ] Credentials secured

---

## 🎉 DEPLOYMENT COMPLETE!

Congratulations! Your ELIS STMS is now live!

**What's Next:**
1. Share URL with stakeholders
2. Gather user feedback
3. Plan feature updates
4. Monitor performance
5. Regular maintenance

---

**Deployment Date:** _______________

**Deployed By:** _______________

**Render URL:** _______________

**GitHub Repo:** _______________

**Team Members:**
- _______________
- _______________
- _______________

---

*Keep this checklist for future deployments and updates!*
