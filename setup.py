#!/usr/bin/env python3
"""
Setup script for CRAWL AI - UX/QA Automation Tool
"""

import os
import sys
import subprocess
import sqlite3

def check_requirements():
    """Check if required packages are installed"""
    print("Checking requirements...")
    
    try:
        import playwright
        print("✓ Playwright installed")
    except ImportError:
        print("✗ Playwright not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
        subprocess.run(["playwright", "install", "chromium"])
    
    try:
        import flask
        print("✓ Flask installed")
    except ImportError:
        print("✗ Flask not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "flask", "flask-cors"])
    
    try:
        import langchain
        print("✓ LangChain installed")
    except ImportError:
        print("✗ LangChain not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "langchain", "langgraph"])
    
    print("✓ All requirements checked")

def setup_database():
    """Initialize the SQLite database"""
    print("Setting up database...")
    
    # Read schema
    with open("schema.sql", "r") as f:
        schema = f.read()
    
    # Create database
    conn = sqlite3.connect("uat.db")
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()
    
    # Check if credentials exist
    cursor.execute("SELECT COUNT(*) FROM credentials")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("No credentials found. You'll need to add them after setup.")
    
    conn.close()
    print("✓ Database initialized")

def create_directories():
    """Create necessary directories"""
    directories = ["screenshots", "logs", "reports", "tools", "agents"]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created {directory}/ directory")

def setup_environment():
    """Create .env file if it doesn't exist"""
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("""# CRAWL AI Configuration
# Add your API keys here:

# Gemini API (Optional)
# GEMINI_API_KEY=your_gemini_api_key_here

# Groq API (Optional)
# GROQ_API_KEY=your_groq_api_key_here

# Note: At least one API key is required for AI analysis
# If no API keys are provided, basic analysis will still work
""")
        print("✓ Created .env file")
        print("⚠️  Please add your API keys to .env file for full AI analysis")
    else:
        print("✓ .env file already exists")

def main():
    print("="*60)
    print("CRAWL AI - UX/QA Automation Tool Setup")
    print("="*60)
    
    # Create directories
    create_directories()
    
    # Setup database
    setup_database()
    
    # Setup environment
    setup_environment()
    
    # Check requirements
    check_requirements()
    
    print("\n" + "="*60)
    print("SETUP COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("1. Add API keys to .env file (optional)")
    print("2. Run: python insert_credentials.py (to add test credentials)")
    print("3. Run: python app.py (to start the server)")
    print("4. Open index.html in your browser")
    print("\nOr run: python main.py (for command-line testing)")
    print("="*60)

if __name__ == "__main__":
    main()