# Google OAuth Setup Guide - Phase 2

## Date: May 18, 2026

---

## 📋 OVERVIEW

This guide will help you set up Google OAuth (Sign in with Google) for your STMS application.

**Benefits**:
- ✅ One-click registration/login
- ✅ No need to remember passwords
- ✅ Auto-fill name and email from Google account
- ✅ More secure authentication
- ✅ Better user experience

---

## 🔑 STEP 1: GET GOOGLE OAUTH CREDENTIALS

### A. Go to Google Cloud Console

1. Visit: https://console.cloud.google.com/
2. Sign in with your Google account (use: elis.stms.otp@gmail.com)

### B. Create a New Project (or use existing)

1. Click on the project dropdown (top left)
2. Click "New Project"
3. Project Name: **STMS Elis**
4. Click "Create"
5. Wait for project creation (takes a few seconds)

### C. Enable Google+ API

1. In the left sidebar, go to: **APIs & Services** > **Library**
2. Search for: **Google+ API**
3. Click on it
4. Click **Enable**

### D. Configure OAuth Consent Screen

1. Go to: **APIs & Services** > **OAuth consent screen**
2. Choose: **External** (for testing with any Google account)
3. Click **Create**

**Fill in the form**:
- **App name**: STMS - Smart Tenant Management System
- **User support email**: elis.stms.otp@gmail.com
- **App logo**: (optional, skip for now)
- **Application home page**: http://127.0.0.1:5001
- **Authorized domains**: (leave empty for localhost testing)
- **Developer contact**: elis.stms.otp@gmail.com
- Click **Save and Continue**

**Scopes** (Step 2):
- Click **Add or Remove Scopes**
- Select:
  - `userinfo.email`
  - `userinfo.profile`
  - `openid`
- Click **Update**
- Click **Save and Continue**

**Test Users** (Step 3):
- Click **Add Users**
- Add your test email addresses
- Click **Save and Continue**

**Summary** (Step 4):
- Review and click **Back to Dashboard**

### E. Create OAuth 2.0 Credentials

1. Go to: **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Application type: **Web application**
4. Name: **STMS Web Client**

**Authorized JavaScript origins**:
```
http://127.0.0.1:5001
http://localhost:5001
```

**Authorized redirect URIs**:
```
http://127.0.0.1:5001/auth/google/callback
http://localhost:5001/auth/google/callback
```

5. Click **Create**
6. **IMPORTANT**: Copy your credentials:
   - **Client ID**: (looks like: 123456789-abc123.apps.googleusercontent.com)
   - **Client Secret**: (looks like: GOCSPX-abc123xyz)

---

## 🔧 STEP 2: ADD CREDENTIALS TO .ENV FILE

Add these lines to your `.env` file:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://127.0.0.1:5001/auth/google/callback
```

**Replace**:
- `your_client_id_here` with your actual Client ID
- `your_client_secret_here` with your actual Client Secret

---

## 📦 STEP 3: INSTALL REQUIRED LIBRARY

Run this command in your terminal:

```bash
.venv/bin/pip install authlib requests
```

This will install:
- `authlib` - OAuth library for Flask
- `requests` - HTTP library (if not already installed)

---

## 🎯 WHAT I WILL IMPLEMENT

Once you provide the credentials, I will:

### 1. **Backend Routes** (`app/blueprints/auth/routes.py`)
- `/auth/google` - Initiates Google OAuth flow
- `/auth/google/callback` - Handles OAuth callback
- Auto-create user account from Google data
- Auto-login after successful OAuth

### 2. **OAuth Configuration** (`app/__init__.py`)
- Configure Authlib OAuth client
- Set up Google OAuth provider
- Handle token management

### 3. **User Model Updates** (`app/models.py`)
- Add `google_id` field to User model
- Add `oauth_provider` field (google/email)
- Migration script to update database

### 4. **Frontend Updates**
- Enable "Continue with Google" button
- Remove "Coming Soon" text
- Add loading state during OAuth
- Handle OAuth errors gracefully

### 5. **Security Features**
- CSRF protection
- State parameter validation
- Secure token storage
- Email verification bypass for Google users

---

## 🔒 SECURITY CONSIDERATIONS

### What I Will Implement:
- ✅ State parameter to prevent CSRF attacks
- ✅ Secure token handling
- ✅ Email verification (Google emails are pre-verified)
- ✅ Unique Google ID storage
- ✅ Prevent duplicate accounts

### What You Should Know:
- Google OAuth is more secure than password-based auth
- Users can revoke access anytime from their Google account
- We only request email and profile info (no sensitive data)

---

## 📊 DATABASE CHANGES NEEDED

### New Columns in `users` table:
```sql
ALTER TABLE users 
ADD COLUMN google_id VARCHAR(255) UNIQUE NULL,
ADD COLUMN oauth_provider VARCHAR(50) DEFAULT 'email',
ADD COLUMN is_oauth_verified BOOLEAN DEFAULT FALSE;
```

**Fields**:
- `google_id`: Unique Google user ID
- `oauth_provider`: 'google' or 'email'
- `is_oauth_verified`: TRUE for Google users (skip email verification)

---

## 🎨 USER FLOW

### New User (First Time with Google):
1. Click "Continue with Google"
2. Redirected to Google login page
3. User logs in with Google account
4. Google asks for permission (email, profile)
5. User clicks "Allow"
6. Redirected back to STMS
7. **Account automatically created**
8. User logged in and redirected to dashboard

### Existing User (Already Registered):
1. Click "Continue with Google"
2. Redirected to Google login page
3. User logs in with Google account
4. Redirected back to STMS
5. **Automatically logged in**
6. Redirected to dashboard

### Linking Accounts:
If user already has an email account with the same email:
- Option 1: Link Google account to existing account
- Option 2: Show error and ask to login with email first

---

## 🧪 TESTING CHECKLIST

After implementation, test these scenarios:

### New User Registration:
- [ ] Click "Continue with Google"
- [ ] Redirected to Google login
- [ ] Login with Google account
- [ ] Grant permissions
- [ ] Account created automatically
- [ ] Logged in successfully
- [ ] Name and email auto-filled
- [ ] No email verification needed

### Existing User Login:
- [ ] Click "Continue with Google"
- [ ] Redirected to Google login
- [ ] Login with same Google account
- [ ] Logged in successfully
- [ ] Redirected to dashboard

### Error Handling:
- [ ] User cancels Google login → Show error message
- [ ] Network error → Show error message
- [ ] Invalid credentials → Show error message
- [ ] Duplicate email → Handle gracefully

---

## 📝 NEXT STEPS

### What You Need to Do:

1. **Get Google OAuth Credentials**:
   - Follow Step 1 above
   - Get Client ID and Client Secret
   - Add to `.env` file

2. **Install Library**:
   ```bash
   .venv/bin/pip install authlib requests
   ```

3. **Tell Me When Ready**:
   - Once you have the credentials in `.env`
   - I will implement all the code
   - I will create the migration script
   - I will test everything

### What I Will Do:

1. **Backend Implementation**:
   - OAuth routes
   - User creation logic
   - Token handling
   - Error handling

2. **Database Migration**:
   - Add new columns
   - Update existing users
   - Create indexes

3. **Frontend Updates**:
   - Enable Google button
   - Add loading states
   - Handle errors

4. **Testing**:
   - Test all scenarios
   - Verify security
   - Check error handling

---

## ⚠️ IMPORTANT NOTES

### For Development (localhost):
- Use `http://127.0.0.1:5001` (not `localhost`)
- Add both to authorized origins
- Test with your own Google account first

### For Production (when deploying):
- Update redirect URI to your domain
- Update authorized origins
- Re-verify OAuth consent screen
- Test thoroughly before going live

### Privacy & Terms:
- You'll need to create Terms & Conditions page
- You'll need to create Privacy Policy page
- Google requires these for OAuth consent screen

---

## 🎉 BENEFITS OF GOOGLE OAUTH

### For Users:
- ✅ Faster registration (1 click)
- ✅ No password to remember
- ✅ More secure
- ✅ Auto-fill name and email
- ✅ Can revoke access anytime

### For You (Admin):
- ✅ Less password reset requests
- ✅ Verified email addresses
- ✅ Better user experience
- ✅ Modern authentication
- ✅ Trusted by users

---

## 📞 NEED HELP?

If you encounter issues:

1. **Can't find Google Cloud Console**:
   - Go to: https://console.cloud.google.com/

2. **Can't create project**:
   - Make sure you're logged in
   - Check if you have permissions

3. **OAuth consent screen issues**:
   - Choose "External" for testing
   - Add test users if needed

4. **Credentials not working**:
   - Double-check Client ID and Secret
   - Verify redirect URI matches exactly
   - Check authorized origins

---

## 🚀 READY TO START?

Once you have:
- ✅ Google Client ID
- ✅ Google Client Secret
- ✅ Added to `.env` file
- ✅ Installed `authlib` library

**Tell me and I'll implement Phase 2 completely!** 🎊

---

*Guide created: May 18, 2026*
*STMS - Smart Tenant Management System*
*Phase 2: Google OAuth Setup*
