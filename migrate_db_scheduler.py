"""
Database migration: Add scheduled_tests table for scheduled testing feature.
"""

import sqlite3
from db import get_db

def migrate():
    """Add scheduled_tests table to database"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Create scheduled_tests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_url TEXT NOT NULL,
                task_description TEXT,
                frequency TEXT NOT NULL,  -- 'daily', 'weekly', 'interval', 'once'
                schedule_time TEXT,  -- HH:MM format for daily/weekly
                interval_hours INTEGER,  -- For interval frequency
                interval_minutes INTEGER,  -- For interval frequency
                days_of_week TEXT,  -- Comma-separated days for weekly (e.g., 'monday,wednesday')
                schedule_date TEXT,  -- ISO format date for one-time schedules
                enabled INTEGER DEFAULT 1,  -- 1 = enabled, 0 = disabled
                status TEXT DEFAULT 'pending',  -- 'pending', 'running', 'success', 'failed'
                last_run_time TEXT,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                app_name TEXT  -- Derived from site_url, cached for performance
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_tests_enabled 
            ON scheduled_tests(enabled)
        """)
        
        conn.commit()
        print("✓ Migration completed: scheduled_tests table created")
        
    except sqlite3.OperationalError as e:
        if "already exists" in str(e).lower():
            print("✓ Migration already applied: scheduled_tests table exists")
        else:
            print(f"✗ Migration error: {e}")
            conn.rollback()
    except Exception as e:
        print(f"✗ Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

