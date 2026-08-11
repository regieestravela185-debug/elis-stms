# 🚀 Paano I-run ang ELIS System

## PINAKAMADALI - Gamit ang Start Script

### Para sa Mac/Linux:
```bash
./start.sh
```

### Para sa Windows:
```bash
start.bat
```

---

## MANUAL NA PARAAN

### Paraan 1: I-activate ang Virtual Environment
```bash
# Mac/Linux
source .venv/bin/activate
python run.py

# Windows
.venv\Scripts\activate
python run.py
```

### Paraan 2: Direktang Run (Walang Activation)
```bash
# Mac/Linux
.venv/bin/python run.py

# Windows
.venv\Scripts\python.exe run.py
```

---

## 📍 Access ang System

Pagkatapos mag-start, i-access ang system sa:
- **URL:** http://localhost:5001
- **Port:** 5001

---

## ⚠️ Common Issues

### Error: "No such file or directory: /opt/homebrew/bin/brew"
- **Solusyon:** Ignore lang, hindi naman kailangan para tumakbo ang app

### Error: "AssertionError" sa SQLAlchemy
- **Solusyon:** HUWAG gumamit ng `python3` command. Gumamit ng `./start.sh` o `.venv/bin/python`
- **Dahilan:** Python 3.13 ay hindi pa compatible sa SQLAlchemy. Ang .venv ay gumagamit ng Python 3.12

### Error: "ModuleNotFoundError"
- **Solusyon:** I-install ang requirements:
  ```bash
  .venv/bin/pip install -r requirements.txt
  ```

### Error: Database connection
- **Solusyon:** I-check ang .env file kung may correct na database credentials

---

## 🛠 Maintenance Commands

### I-update ang Dependencies
```bash
.venv/bin/pip install -r requirements.txt
```

### I-check ang Python Version
```bash
.venv/bin/python --version
```

### I-check kung Installed ba ang lahat
```bash
.venv/bin/pip list
```

---

## 💡 Tips

1. **Always use the virtual environment** - Huwag gumamit ng system Python (python3)
2. **Check .env file** - Siguraduhing may database credentials
3. **Use start.sh** - Pinakamadaling paraan para mag-run

---

## 📞 Kung May Problem Pa Rin

1. I-check kung naka-on ba ang MySQL/MariaDB
2. I-check kung correct ba ang database name sa .env
3. Tingnan ang error message carefully
4. Ask for help! 😊
