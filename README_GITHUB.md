# 🏢 STMS - Smart Tenant Management System (The Elis Center)

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)
![PostgreSQL](https://img.shields.io/badge/database-postgresql-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A modern, AI-powered tenant management system for commercial and residential properties. Built with Flask, featuring real-time notifications, OCR ID verification, facial recognition, and smart analytics.

## ✨ Features

### 🔐 Authentication & Security
- **Multi-role system**: Admin, Tenant, User roles with role-based access control
- **Google OAuth 2.0** integration for quick sign-up/login
- **Email verification** with OTP (One-Time Password)
- **Password reset** via email
- **Session management** with remember-me functionality

### 👤 User Management
- User registration with email validation (@gmail.com)
- Profile management with avatar upload
- Account status tracking (active, banned)
- Last login tracking

### 🏠 Property Management
- **Multi-building support** with floor-based unit organization
- **Unit management**: Create, update, archive units
- **Dynamic pricing** with configurable rates
- **Unit status tracking**: Available, Occupied, Reserved, Under Maintenance
- **Floor plan visualization**

### 📝 Reservation System
- **Online reservation** with ID verification
- **OCR ID scanning** - Automatically extracts information from Philippine IDs:
  - National ID, UMID, PhilHealth, Driver's License
  - Passport, SSS, Postal ID, PRC ID, Voter's ID, TIN ID
- **Document uploads** with security checks
- **Auto-cancellation** for unpaid reservations (configurable hours)
- **Reservation status tracking**: Pending, Approved, Rejected, Cancelled

### 💰 Payment Management
- **Payment tracking** with multiple payment methods
- **Security deposit** management
- **Payment history** and receipts
- **Ledger system** for financial tracking
- **Late payment alerts**

### 🔔 Smart Notifications
- **Real-time notifications** via Flask-SocketIO
- **Email notifications** for important events
- **In-app notification center**
- **Notification preferences**

### 📊 Analytics & Reporting
- **Dashboard analytics** with charts (Chart.js)
- **Occupancy rates** and revenue tracking
- **Tenant analytics**
- **Payment reports**

### 🤖 AI Features
- **OCR ID Verification** - Automatic ID information extraction
- **Document authenticity checks**
- **Predictive analytics** for tenant behavior
- **Smart search** with fuzzy matching

### 📱 Progressive Web App (PWA)
- **Installable** on mobile and desktop
- **Offline support**
- **Service worker** for caching
- **Mobile-responsive** design

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL database (or Supabase account)
- Gmail account (for SMTP email sending)
- Google Cloud project (for OAuth - optional)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/ElisSystem.git
cd ElisSystem
```

2. **Create virtual environment**
```bash
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:
```env
SECRET_KEY=your-secret-key-here
DB_TYPE=postgresql
DB_HOST=your-database-host
DB_PORT=5432
DB_NAME=postgres
DB_USER=your-db-user
DB_PASSWORD=your-db-password
MAIL_USERNAME=your-gmail@gmail.com
MAIL_PASSWORD=your-app-password
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:5001/auth/google/callback
```

5. **Set up the database**
```bash
# Import the SQL schema
psql -h your-host -U your-user -d your-database -f database/stms_elis_postgresql_FULL.sql
```

6. **Run the application**
```bash
python3.11 run.py
```

7. **Access the application**
```
http://127.0.0.1:5001
```

**Default Admin Account:**
- Email: `admin@gmail.com`
- Password: `admin123`

---

## 📁 Project Structure

```
ElisSystem/
├── app/
│   ├── blueprints/          # Flask blueprints (routes)
│   │   ├── admin/          # Admin panel routes
│   │   ├── api/            # API endpoints
│   │   ├── auth/           # Authentication routes
│   │   ├── public/         # Public pages
│   │   ├── tenant/         # Tenant dashboard
│   │   └── user/           # User dashboard
│   ├── static/             # Static files (CSS, JS, images)
│   │   ├── css/
│   │   ├── js/
│   │   ├── img/
│   │   └── uploads/        # User uploaded files
│   ├── templates/          # Jinja2 templates
│   ├── __init__.py         # App factory
│   ├── config.py           # Configuration
│   ├── models.py           # Database models
│   ├── extensions.py       # Flask extensions
│   ├── ocr.py              # OCR ID verification
│   ├── face_verification.py # Face recognition
│   ├── smart_notifications.py
│   ├── predictive_analytics.py
│   └── security.py         # Security utilities
├── database/               # SQL schemas
├── .env                    # Environment variables (not in git)
├── .env.example            # Example env file
├── requirements.txt        # Python dependencies
├── runtime.txt             # Python version
├── build.sh                # Render build script
└── run.py                  # Application entry point
```

---

## 🚀 Deployment to Render.com (FREE)

### Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ElisSystem.git
git push -u origin main
```

### Step 2: Deploy on Render

1. Create account at [render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `elis-stms`
   - **Environment**: `Python 3`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn run:app`
   - **Plan**: `Free`

5. Add environment variables (copy from your `.env`)
6. Update `GOOGLE_REDIRECT_URI` to your Render URL
7. Click "Create Web Service"

**Your app will be live at:** `https://elis-stms.onrender.com`

---

## 👥 For Team Members

### How to Contribute

1. **Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/ElisSystem.git
cd ElisSystem
```

2. **Create a branch for your feature**
```bash
git checkout -b feature/your-feature-name
```

3. **Make your changes and commit**
```bash
git add .
git commit -m "Add: your feature description"
git push origin feature/your-feature-name
```

4. **Create Pull Request** on GitHub

---

## 📚 Tech Stack

**Backend:**
- Flask 3.0.0
- SQLAlchemy (ORM)
- PostgreSQL (Supabase)
- Flask-Login (Auth)
- Flask-Mail (Email)
- APScheduler (Tasks)

**Frontend:**
- Jinja2 (Templates)
- Vanilla JavaScript
- Chart.js (Charts)
- CSS3

**AI/ML:**
- Tesseract OCR
- OpenCV
- DeepFace
- NLTK
- scikit-learn

**Real-time:**
- Flask-SocketIO

---

## 🔐 Security Features

- Password hashing (Werkzeug)
- CSRF protection (Flask-WTF)
- Session management (Flask-Login)
- Email validation
- Input sanitization
- File upload validation
- Role-based access control

---

## 📝 License

MIT License - See LICENSE file for details

---

## 🎓 Academic Project

This is a thesis/capstone project for educational purposes.

---

## 🙏 Acknowledgments

- The Elis Center
- Flask community
- Supabase
- Render.com

---

**⭐ Star this repo if you find it helpful!**
