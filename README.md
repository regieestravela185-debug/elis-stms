# 🏢 ELIS - Smart Tenant Management System (STMS)

Web-based tenant + reservation management system for **The Elis Center** - Commercial and Residences.

![Python](https://img.shields.io/badge/Python-3.12.6-blue)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-blue)
![License](https://img.shields.io/badge/License-Private-red)

---

## 🌟 Features

### Core Functionality
- 👤 **Multi-Role Authentication** - Admin, Tenant, User roles with Google OAuth
- 🏢 **Building Management** - Multiple buildings, units, and floor plans
- 📝 **Tenant Profiles** - Complete tenant information and lease tracking
- 💰 **Payment Management** - Rent, deposits, utility bills, and payment history
- 📊 **Reservation System** - Unit reservations with auto-cancellation
- 📄 **Document Management** - Upload and track leases, bills, IDs
- 🔔 **Smart Notifications** - Real-time alerts via Socket.IO
- 📈 **Analytics Dashboard** - Revenue reports, occupancy rates, trends
- 🔐 **Security** - Face verification, blockchain audit logs, OTP verification

### AI & Emerging Tech
- 🤖 **NLP Chatbot** - Tenant support assistant
- 📷 **Face Verification** - Biometric authentication (DeepFace)
- 🧠 **Predictive Analytics** - Occupancy and revenue forecasting
- 📝 **OCR Processing** - Automatic document text extraction
- 🔗 **Blockchain Logging** - Immutable audit trail

---

## 🚀 Tech Stack

- **Backend:** Flask 3.0.0 (Python 3.12.6)
- **Database:** PostgreSQL (Supabase) / MySQL (Legacy)
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
- **Real-time:** Flask-SocketIO + Eventlet
- **Authentication:** Flask-Login + Google OAuth (Authlib)
- **Email:** Flask-Mail (Gmail SMTP)
- **AI/ML:** DeepFace, OpenCV, NLTK, spaCy, scikit-learn
- **Deployment:** Render (Web Service)
- **Version Control:** Git + GitHub

---

## 📋 Prerequisites

- Python 3.12.6
- Git
- PostgreSQL database (Supabase recommended)
- Gmail account (for email notifications)
- Google Cloud Project (for OAuth - optional)

---

## 🏃 Quick Start (Local Development)

### 1. Clone Repository
```bash
git clone https://github.com/YOUR-USERNAME/elis-stms.git
cd elis-stms
```

### 2. Create Virtual Environment
```bash
# macOS/Linux
python3.12 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables
```bash
cp .env.example .env
```

Then edit `.env` with your actual credentials:
- Supabase database connection
- Gmail SMTP credentials
- Google OAuth credentials
- Secret keys

**Ask repository owner for credentials if you're a collaborator!**

### 5. Run Application
```bash
python run.py
```

Open browser: `http://127.0.0.1:5000`

---

## 🌐 Deployment

### Deploy to Render

**📖 Complete Guide:** [DEPLOYMENT_RENDER.md](DEPLOYMENT_RENDER.md)

**Quick Steps:**
1. Push code to GitHub
2. Create Render account
3. Connect GitHub repository
4. Add environment variables
5. Deploy!

**⚡ Quick Reference:** [DEPLOY_QUICK_REFERENCE.md](DEPLOY_QUICK_REFERENCE.md)

---

## 👥 Team Collaboration

### For Repository Owner
**📖 Complete Setup Guide:** [GITHUB_SETUP.md](GITHUB_SETUP.md)

### For Collaborators
1. Accept GitHub invitation
2. Clone repository
3. Setup virtual environment
4. Install dependencies
5. Copy `.env.example` to `.env`
6. Get credentials from repository owner
7. Start developing!

### Git Workflow
```bash
# Before starting work
git pull origin main

# After making changes
git add .
git commit -m "Descriptive commit message"
git push origin main
```

**Pro Tip:** Use feature branches for major changes!

---

## 📁 Project Structure

```
elis-stms/
├── app/
│   ├── blueprints/         # Route handlers
│   │   ├── admin/         # Admin routes
│   │   ├── tenant/        # Tenant routes
│   │   ├── auth/          # Authentication routes
│   │   ├── api/           # API endpoints
│   │   └── public/        # Public routes
│   ├── static/            # CSS, JS, images
│   │   ├── css/
│   │   ├── js/
│   │   ├── img/
│   │   └── uploads/       # User uploads (gitignored)
│   ├── templates/         # Jinja2 templates
│   ├── models.py          # Database models
│   ├── config.py          # App configuration
│   ├── extensions.py      # Flask extensions
│   ├── security.py        # Password hashing, OTP
│   ├── face_verification.py
│   ├── nlp_chatbot.py
│   ├── ocr.py
│   ├── predictive_analytics.py
│   ├── smart_notifications.py
│   ├── socket_events.py
│   └── jobs.py            # Background tasks
├── database/              # SQL schemas
├── run.py                 # Application entry point
├── requirements.txt       # Python dependencies
├── runtime.txt            # Python version (Render)
├── render.yaml            # Render configuration
├── .env.example           # Environment template
├── .gitignore             # Git ignore rules
└── README.md              # This file
```

---

## 🔑 Default Accounts

After database setup, default admin account:
- **Email:** `admin@gmail.com`
- **Password:** `Admin123!`

**⚠️ Change password immediately after first login!**

---

## 🗄️ Database

### Supabase PostgreSQL (Recommended)
- Cloud-hosted PostgreSQL
- Automatic backups
- No local server needed
- Free tier available

**Schema:** `database/stms_elis_postgresql_FULL.sql`

### MySQL (Legacy - XAMPP)
- Local development only
- Requires XAMPP running

**Schema:** `database/stms_elis.sql`

**Migration Guide:** [SUPABASE_MIGRATION_GUIDE.md](SUPABASE_MIGRATION_GUIDE.md)

---

## 📚 Documentation

- 📖 [GitHub Setup Guide](GITHUB_SETUP.md) - Team collaboration
- 🚀 [Render Deployment Guide](DEPLOYMENT_RENDER.md) - Full deployment
- ⚡ [Quick Deploy Reference](DEPLOY_QUICK_REFERENCE.md) - Command cheatsheet
- 🗄️ [Supabase Migration Guide](SUPABASE_MIGRATION_GUIDE.md) - Database setup
- 🔐 [Google OAuth Setup](GOOGLE_OAUTH_SETUP_GUIDE.md) - OAuth configuration
- ✅ [Migration Complete](MIGRATION_COMPLETE.md) - Migration documentation

---

## 🛠️ Development

### Install New Package
```bash
pip install package-name
pip freeze > requirements.txt
```

### Database Schema Changes
1. Update `app/models.py`
2. Create migration SQL script
3. Run script in Supabase SQL Editor
4. Update `database/stms_elis_postgresql_FULL.sql`

### Testing Locally
```bash
# Run application
python run.py

# Access at http://127.0.0.1:5000
```

---

## 🔐 Environment Variables

Required variables in `.env`:

### Database
```env
DB_TYPE=postgresql
DB_HOST=aws-0-ap-southeast-1.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.your-project-ref
DB_PASSWORD=your-supabase-password
```

### Flask
```env
FLASK_ENV=development
SECRET_KEY=your-secret-key
```

### Email (Gmail)
```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
```

### Google OAuth (Optional)
```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

**See `.env.example` for complete list**

---

## 🐛 Troubleshooting

### Database Connection Failed
- Check Supabase credentials
- Verify internet connection
- Check if Supabase project is active

### Module Not Found
```bash
pip install -r requirements.txt
```

### Permission Denied
- Check file permissions
- Make sure virtual environment is activated

### Google OAuth Error
- Verify redirect URIs in Google Console
- Check CLIENT_ID and CLIENT_SECRET

**More help:** Check documentation files or open an issue

---

## 📊 Features Roadmap

- [ ] Custom domain support
- [ ] SMS notifications
- [ ] Mobile app (React Native)
- [ ] Automated rent reminders
- [ ] Online payment gateway integration
- [ ] Tenant mobile app
- [ ] Advanced analytics dashboards
- [ ] Multi-language support

---

## 🤝 Contributing

This is a private academic project for The Elis Center.

**For Team Members:**
1. Create feature branch
2. Make changes
3. Test thoroughly
4. Create Pull Request
5. Wait for review
6. Merge after approval

---

## 📄 License

Private - Academic Project
© 2026 The Elis Center Development Team

---

## 👨‍💻 Team

- **Lead Developer:** Regie
- **Contributors:** [Add team members here]

---

## 📞 Support

For questions or issues:
- Check documentation files
- Ask in team chat
- Contact repository owner

---

## 🙏 Acknowledgments

- The Elis Center for project opportunity
- Supabase for database hosting
- Render for web hosting
- Google Cloud for OAuth services
- Open source community

---

**Built with ❤️ for The Elis Center**

