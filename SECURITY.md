# ELIS STMS Security Features

## Implemented Security Measures

### 1. Rate Limiting

**Login Protection:**
- Maximum 5 failed login attempts per email/IP
- 15-minute lockout after exceeding limit
- Attempts reset after 30 minutes of inactivity
- Counter shows remaining attempts to user

**Registration Protection:**
- Maximum 5 registration attempts per hour per IP
- Prevents mass account creation
- Stricter limits than login to prevent abuse

**OTP Verification Protection:**
- Maximum 5 failed OTP attempts
- 15-minute lockout after exceeding limit
- Applies to both email-based and registration OTP
- Shows remaining attempts to user

**OTP Resend Protection:**
- Maximum 3 OTP resend requests per 10 minutes
- Prevents OTP flooding attacks
- Prevents email spam

**General API Rate Limiting:**
- 200 requests per day per IP
- 50 requests per hour per IP
- Protects against DDoS and brute force

### 2. Security Headers

**XSS Protection:**
- `X-Content-Type-Options: nosniff` - Prevents MIME-type sniffing
- `X-XSS-Protection: 1; mode=block` - Enables browser XSS filtering
- Content Security Policy (CSP) - Restricts resource loading

**Clickjacking Protection:**
- `X-Frame-Options: SAMEORIGIN` - Prevents iframe embedding from other domains

**Content Security Policy:**
- Scripts: Self, inline, Google OAuth, CDNs
- Styles: Self, inline, Google Fonts
- Fonts: Self, Google Fonts, CDNs
- Images: All sources (for user uploads)
- Frames: Google OAuth only

**Other Headers:**
- `Referrer-Policy: strict-origin-when-cross-origin` - Controls referrer information
- `Permissions-Policy` - Disables geolocation, microphone, camera

### 3. Session Security

**Session Configuration:**
- `SESSION_COOKIE_HTTPONLY = True` - JavaScript cannot access cookies
- `SESSION_COOKIE_SAMESITE = "Lax"` - CSRF protection
- `SESSION_COOKIE_SECURE = True` (production) - HTTPS only
- `PERMANENT_SESSION_LIFETIME = 24 hours` - Automatic expiration
- Custom session cookie name for isolation

**Session Invalidation:**
- Sessions cleared on server restart (with pending_registration preservation)
- Automatic logout on boot_id mismatch
- Session data encrypted with SECRET_KEY

### 4. Password Security

**Password Requirements:**
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character (!@#$%^&*(),.?":{}|<>)

**Password Storage:**
- Bcrypt hashing with salt
- Work factor adjustable for future security needs
- Never stored in plain text
- Never logged or transmitted unencrypted

### 5. Email Verification

**Two-Factor Registration:**
- OTP sent to email before account activation
- 10-minute OTP expiration
- Rate-limited verification attempts
- Prevents fake account creation

**OTP Security:**
- 6-digit random numeric code
- Cryptographically secure generation
- Single-use tokens
- Automatic expiration

### 6. Account Protection

**Ban System:**
- Admins can ban abusive accounts
- Banned users cannot login
- Ban reason tracked for auditing
- Automatic rejection with clear message

**Email Restrictions:**
- Only @gmail.com emails allowed
- Reduces spam and fake accounts
- Easy to verify ownership

### 7. Security Logging

**Audit Trail:**
- Failed login attempts logged with IP
- Account lockouts logged
- OTP verification failures logged
- Successful authentications logged
- Banned login attempts logged

**Log Information:**
- Timestamp
- Event type
- Email/user identifier
- IP address
- User agent (future)

### 8. Google OAuth Security

**OAuth 2.0 Implementation:**
- Server-side token verification
- Account linking for existing emails
- Automatic email verification (trusted provider)
- Forced account selection prompt

### 9. Input Validation

**Email Validation:**
- Format validation
- Domain restriction (@gmail.com)
- SQL injection prevention (parameterized queries)

**Form Validation:**
- Required fields checked
- Length limits enforced
- Type validation
- XSS prevention (escaped output)

### 10. HTTPS & Transport Security

**Production Requirements:**
- HTTPS enforced (SESSION_COOKIE_SECURE)
- Secure cookie transmission
- TLS 1.2+ recommended

## Security Configuration

### Environment Variables

```env
# Required for production
SECRET_KEY=<strong-random-key>
SESSION_COOKIE_SECURE=1  # Set to 1 in production (HTTPS)

# Database (use strong passwords)
DB_PASSWORD=<strong-password>

# API Keys (keep secret)
BREVO_API_KEY=<your-key>
GOOGLE_CLIENT_SECRET=<your-secret>
```

### Recommended Additional Security (Future Enhancements)

1. **CAPTCHA Integration**
   - Add Google reCAPTCHA after 2 failed login attempts
   - Prevents automated attacks

2. **Redis for Rate Limiting**
   - Replace in-memory storage with Redis
   - Allows distributed rate limiting
   - Persists across server restarts

3. **Two-Factor Authentication (2FA)**
   - Add TOTP (Google Authenticator)
   - SMS backup codes
   - Recovery codes

4. **IP Whitelisting/Blacklisting**
   - Admin panel to manage IP access
   - Automatic blacklisting after repeated attacks
   - Country-based restrictions

5. **Security Monitoring**
   - Real-time alerts for suspicious activity
   - Dashboard for security metrics
   - Automated threat response

6. **Database Security**
   - Encrypted backups
   - Regular security audits
   - Principle of least privilege for DB users

7. **API Security**
   - JWT tokens for API authentication
   - API key rotation
   - Scope-based permissions

8. **File Upload Security**
   - Virus scanning
   - File type validation
   - Size limits enforced
   - Sandboxed storage

## Security Best Practices for Deployment

1. **Use strong SECRET_KEY**
   ```python
   import secrets
   print(secrets.token_hex(32))
   ```

2. **Enable HTTPS**
   - Use Let's Encrypt for free SSL
   - Set SESSION_COOKIE_SECURE=1

3. **Regular Updates**
   - Keep Flask and dependencies updated
   - Monitor security advisories
   - Apply patches promptly

4. **Database Security**
   - Use connection pooling with Supabase
   - Enable SSL for database connections
   - Restrict database access by IP

5. **Backup Strategy**
   - Daily automated backups
   - Encrypted backup storage
   - Test restore procedures

6. **Monitoring**
   - Set up error tracking (Sentry)
   - Monitor failed login attempts
   - Alert on suspicious patterns

7. **Incident Response**
   - Have a security incident plan
   - Document breach procedures
   - Maintain contact information

## Security Audit Checklist

- [ ] SECRET_KEY is strong and unique
- [ ] HTTPS enabled in production
- [ ] SESSION_COOKIE_SECURE=1 in production
- [ ] Database uses strong password
- [ ] API keys are not in git repository
- [ ] Rate limiting is working
- [ ] Security headers are applied
- [ ] Password requirements enforced
- [ ] OTP expiration working
- [ ] Failed attempts logged
- [ ] Account lockout working
- [ ] Ban system functional
- [ ] Input validation working
- [ ] SQL injection tests passed
- [ ] XSS tests passed
- [ ] CSRF protection enabled

## Reporting Security Issues

If you discover a security vulnerability, please email:
- **Email:** admin@eliscenter.com (replace with actual)
- **Do not** open public GitHub issues for security vulnerabilities
- Include detailed steps to reproduce
- Allow 48 hours for initial response

## Compliance

### GDPR Considerations
- User data encrypted at rest
- Right to deletion implemented (archive system)
- Data minimization practiced
- Consent tracking for data processing

### Best Practices Followed
- OWASP Top 10 protections
- Secure coding standards
- Regular security reviews
- Penetration testing recommended

---

**Last Updated:** August 12, 2026
**Security Version:** 1.0
**Contact:** ELIS STMS Development Team
