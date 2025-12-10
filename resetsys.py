#!/usr/bin/env python3
"""
Reset the CRAWL AI system
"""

import os
import sqlite3
import shutil
import time

def reset_database():
    """Reset the database"""
    print("Resetting database...")
    
    # Backup old database if exists
    if os.path.exists("uat.db"):
        backup_name = f"uat_backup_{int(time.time())}.db"
        os.rename("uat.db", backup_name)
        print(f"Backed up database to {backup_name}")
    
    # Create new database from schema
    with open("schema.sql", "r") as f:
        schema = f.read()
    
    conn = sqlite3.connect("uat.db")
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()
    conn.close()
    
    print("Database reset complete")

def clear_directories():
    """Clear temporary directories"""
    directories = ["screenshots", "logs", "reports"]
    
    for directory in directories:
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
                print(f"Cleared {directory}/")
            except:
                pass
        
        os.makedirs(directory, exist_ok=True)
        print(f"Created {directory}/")

def kill_processes():
    """Kill any running Python processes"""
    import subprocess
    import sys
    
    if sys.platform == "win32":
        # Windows
        subprocess.run(["taskkill", "/F", "/IM", "python.exe"], 
                      capture_output=True, shell=True)
    else:
        # Unix/Linux/Mac
        subprocess.run(["pkill", "-f", "app.py"], 
                      capture_output=True)
    
    print("Killed running processes")
    time.sleep(2)

def main():
    print("="*60)
    print("CRAWL AI System Reset")
    print("="*60)
    
    kill_processes()
    clear_directories()
    reset_database()
    
    print("\n" + "="*60)
    print("SYSTEM RESET COMPLETE")
    print("="*60)
    print("\nTo start fresh:")
    print("1. Run: python setup.py")
    print("2. Run: python app.py")
    print("3. Open index.html in browser")
    print("="*60)

if __name__ == "__main__":
    main()