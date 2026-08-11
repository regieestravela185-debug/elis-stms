#!/bin/bash

# ELIS System Startup Script
# Simple script to run the ELIS system with the correct Python environment

echo "🚀 Starting ELIS System..."
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found!"
    echo "Please create it first with: python3.12 -m venv .venv"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Please create .env file with your configuration"
    echo ""
fi

echo "✅ Using Python from virtual environment (.venv)"
echo "✅ Python version: $(.venv/bin/python --version)"
echo ""
echo "📡 Starting server on http://localhost:5001"
echo "Press Ctrl+C to stop the server"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run the application
.venv/bin/python run.py
