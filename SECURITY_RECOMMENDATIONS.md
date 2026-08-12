# Additional Security Recommendations for ELIS STMS

## ✅ Already Implemented

1. **Rate Limiting** - 5 attempts for login/register/OTP
2. **Account Lockout** - 15-minute lockout after failed attempts
3. **Security Headers** - XSS, Clickjacking, MIME sniffing protection
4. **Session Security** - HttpOnly, SameSite cookies
5. **Password Requirements** - Strong password policy
6. **Security Logging** - Audit trail for failed attempts
7. **Email Verification** - OTP-based two-factor registration
8. **Google OAuth** - Secure third-party authentication

---

## 🎯 High Priority Recommendations

### 1. **CAPTCHA Integration** (Recommended: Google reCAPTCHA v3)

**Why:**
- Prevents automated bots from attacking your system
- Invisible to users (no clicking images)
- Scores each request from 0-1 based on bot likelihood

**Implementation:**
```python
# After 2 failed login attempts, require CAPTCHA
if failed_attempts >= 2:
    # Verify reCAPTCHA token
    response = requests.post('https://www.google.com/recaptcha/api/siteverify', data={
        'secret': RECAPTCHA_SECRET_KEY,
        'response': captcha_token
    })
    if response.json()['score'] < 0.5:
        return "CAPTCHA verification failed"
```

**Setup:**
1. Get keys from https://www.google.com/recaptcha/admin
2. Add to frontend: `<script src="https://www.google.com/recaptcha/api.js"></script>`
3. Add to backend: Verify token on login/register

**Cost:** FREE (up to 1 million assessments/month)

---

### 2. **Redis for Rate Limiting** (Production Must-Have)

**Why:**
- Current in-memory storage is lost on server restart
- Render free tier restarts frequently
- Redis persists rate limit data
- Works across multiple server instances

**Setup:**
```python
# Install: pip install redis
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"  # Or Render Redis addon
)
```

**Render Redis:**
- Add Redis addon in Render dashboard
- Free tier: 25MB storage
- Upgrade to $7/month for 256MB if needed

---

### 3. **Two-Factor Authentication (2FA)** (High Security)

**Why:**
- Even if password is stolen, attacker needs second factor
- Industry standard for secure systems
- Users trust systems with 2FA

**Options:**
- **TOTP (Time-based OTP)**: Google Authenticator, Authy
- **SMS Backup**: Twilio (costs money)
- **Recovery Codes**: For device loss

**Implementation:**
```python
# Install: pip install pyotp
import pyotp

# Generate secret for user
secret = pyotp.random_base32()
totp = pyotp.TOTP(secret)

# Verify token
if totp.verify(user_entered_token):
    # Success
```

**Cost:** 
- TOTP: FREE
- SMS: $0.0075 per message (Twilio)

---

### 4. **Security Monitoring & Alerts** (Important)

**Why:**
- Know when attacks are happening in real-time
- Respond to security incidents faster
- Detect unusual patterns

**Recommendations:**

**A. Sentry (Error & Performance Monitoring)**
- FREE tier: 5,000 events/month
- Captures errors, performance issues
- Email/Slack alerts
- https://sentry.io

```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="your-dsn-here",
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.1  # 10% performance monitoring
)
```

**B. Custom Security Dashboard**
- Track failed login attempts per hour/day
- Show locked accounts
- Geographic distribution of attacks
- Alert when threshold exceeded

**C. Uptime Monitoring**
- UptimeRobot (FREE): https://uptimerobot.com
- Monitors if site is down
- Alerts via email/SMS/Slack

---

### 5. **Database Security Enhancements**

**A. Encrypted Connections**
```python
# Already using Supabase SSL
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?sslmode=require"  # Add this
)
```

**B. Read-Only Database User for Reports**
```sql
CREATE USER readonly WITH PASSWORD 'secure_password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
```

**C. Regular Backups**
- Supabase: Automatic daily backups (included)
- Test restore procedure quarterly
- Keep backups for 30 days minimum

---

### 6. **API Security** (If you add public APIs)

**JWT Tokens:**
```python
from flask_jwt_extended import JWTManager, create_access_token

jwt = JWTManager(app)

# Generate token
access_token = create_access_token(identity=user.id, expires_delta=timedelta(hours=1))
```

**API Rate Limiting:**
```python
@app.route('/api/reservations')
@limiter.limit("30 per minute")  # Stricter for API
@jwt_required()
def api_reservations():
    pass
```

---

### 7. **File Upload Security** (For ID documents, receipts)

**A. Virus Scanning**
```python
# Install: pip install pyclamd
import pyclamd

cd = pyclamd.ClamdUnixSocket()
if cd.scan_file(file_path):
    # File is infected
```

**B. File Type Validation**
```python
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
```

**C. File Size Limits**
```python
# Already set: MAX_CONTENT_LENGTH = 10MB
# Consider lowering to 5MB for better performance
```

---

### 8. **Password Breach Detection** (Nice to have)

**Have I Been Pwned API:**
- Check if password is in known breaches
- FREE API (rate limited)
- Warn users if their password is compromised

```python
import hashlib
import requests

def check_pwned_password(password):
    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    
    response = requests.get(f'https://api.pwnedpasswords.com/range/{prefix}')
    hashes = response.text.split('\n')
    
    for h in hashes:
        if h.split(':')[0] == suffix:
            return True  # Password is breached
    return False
```

---

### 9. **Content Security Policy (CSP) Hardening**

**Current CSP allows 'unsafe-inline' and 'unsafe-eval'**

**Recommendations:**
- Move all inline scripts to external files
- Use nonces for necessary inline scripts
- Remove 'unsafe-eval' if possible

**Better CSP:**
```python
CSP = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{NONCE}' https://cdn.jsdelivr.net https://accounts.google.com; "
    "style-src 'self' 'nonce-{NONCE}' https://fonts.googleapis.com; "
    # ... rest
)
```

---

### 10. **Audit Logging & Compliance**

**GDPR Requirements:**
- [ ] Log user consent for data processing
- [ ] Allow users to download their data
- [ ] Allow users to delete their account (already have archive)
- [ ] Data retention policy (delete after X years)
- [ ] Privacy policy page
- [ ] Cookie consent banner

**Audit Log Table:**
```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INT,
    action VARCHAR(50),  -- 'login', 'register', 'update_profile', 'delete_data'
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 💰 Cost Summary

| Feature | Cost | Priority |
|---------|------|----------|
| Rate Limiting (current) | FREE | ✅ Done |
| reCAPTCHA v3 | FREE | 🔥 High |
| Redis (Render addon) | FREE - $7/mo | 🔥 High |
| 2FA (TOTP) | FREE | ⚠️ Medium |
| SMS 2FA (Twilio) | ~$0.01/message | ❄️ Low |
| Sentry | FREE - $26/mo | ⚠️ Medium |
| UptimeRobot | FREE | ⚠️ Medium |
| ClamAV (virus scan) | FREE | ❄️ Low |
| Supabase backups | FREE (included) | ✅ Done |

**Recommended Budget: $0-7/month** (just Redis if needed)

---

## 🚀 Implementation Priority

### Phase 1 (Now - 1 week)
1. ✅ Rate limiting (DONE)
2. ✅ Security headers (DONE)
3. Add reCAPTCHA v3
4. Set up Sentry error tracking
5. Set up UptimeRobot

### Phase 2 (1-2 weeks)
1. Upgrade to Redis for rate limiting
2. Implement security dashboard
3. Add breach password checking
4. Harden CSP

### Phase 3 (1 month)
1. Add 2FA (TOTP)
2. Implement comprehensive audit logging
3. GDPR compliance features
4. File upload virus scanning

### Phase 4 (Ongoing)
1. Regular security audits
2. Penetration testing
3. Monitor and respond to threats
4. Update dependencies monthly

---

## 🧪 Security Testing Checklist

### Manual Tests
- [ ] Try 5 wrong passwords → Should lock account
- [ ] Wait 15 minutes → Should allow login again
- [ ] Try SQL injection in login form: `' OR '1'='1`
- [ ] Try XSS in name field: `<script>alert('XSS')</script>`
- [ ] Check security headers with: https://securityheaders.com
- [ ] Test HTTPS redirect
- [ ] Verify session expires after 24 hours
- [ ] Check if banned user can login

### Automated Tools
- [ ] OWASP ZAP scan: https://www.zaproxy.org
- [ ] Nikto web scanner: `nikto -h https://your-site.com`
- [ ] SQL injection: `sqlmap -u "https://your-site.com/auth/login" --forms`
- [ ] SSL Labs test: https://www.ssllabs.com/ssltest/

---

## 📞 Security Contacts

**In case of security incident:**

1. **Render Support:**
   - Dashboard: https://dashboard.render.com
   - Support: support@render.com

2. **Supabase Support:**
   - Dashboard: https://app.supabase.com
   - Support: support@supabase.io

3. **Your Team:**
   - Admin Email: [YOUR EMAIL]
   - Phone: [YOUR PHONE]
   - Backup Contact: [BACKUP]

---

## 📚 Resources

**Learning:**
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- Flask Security: https://flask.palletsprojects.com/en/stable/security/
- Python Security: https://python.readthedocs.io/en/stable/library/security_warnings.html

**Tools:**
- Security Headers: https://securityheaders.com
- SSL Labs: https://www.ssllabs.com/ssltest/
- Have I Been Pwned: https://haveibeenpwned.com/API/v3

**Communities:**
- r/netsec: https://reddit.com/r/netsec
- r/flask: https://reddit.com/r/flask
- OWASP Slack: https://owasp.org/slack/invite

---

**Good luck securing your system! 🔒**

*Last updated: August 12, 2026*
