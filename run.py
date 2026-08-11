#!/usr/bin/env python3
"""
ELIS System - Main Application Entry Point

This script automatically checks if you're using the correct Python version
and redirects to the virtual environment if needed.
"""

import os
import sys
import subprocess
from pathlib import Path

# Check if we're running from the virtual environment
def is_venv():
    return hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

# Auto-redirect to virtual environment if not already in it
if __name__ == "__main__" and not is_venv():
    venv_python = Path(__file__).parent / ".venv" / "bin" / "python"
    
    if venv_python.exists():
        print("🔄 Redirecting to virtual environment Python...")
        print(f"   Using: {venv_python}")
        print()
        # Re-run this script with the venv Python
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)
    else:
        print("❌ ERROR: Virtual environment not found!")
        print("   Please run: python3.12 -m venv .venv")
        print("   Then: .venv/bin/pip install -r requirements.txt")
        sys.exit(1)

# Now we're safely in the virtual environment
import warnings
import logging

# Suppress TensorFlow C++ and Python warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # 0=all, 1=info, 2=warning, 3=error only
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
warnings.filterwarnings('ignore', category=UserWarning, module='tensorflow')
logging.getLogger('tensorflow').setLevel(logging.ERROR)

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ELIS SYSTEM STARTING")
    print("=" * 60)
    print(f"✅ Python Version: {sys.version.split()[0]}")
    print(f"✅ Python Path: {sys.executable}")
    print(f"✅ Virtual Environment: {'Yes' if is_venv() else 'No'}")
    
    port = int(os.environ.get("PORT", 5001))
    print(f"✅ Server Port: {port}")
    print()
    print(f"🌐 Access the system at: http://localhost:{port}")
    print("=" * 60)
    print()
    
    # Use socketio.run for WebSocket support with real-time notifications
    socketio.run(app, debug=True, port=port, allow_unsafe_werkzeug=True)
