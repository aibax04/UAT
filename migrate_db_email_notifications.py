"""
Database migration: Add email notification fields to scheduled_tests table.
"""

import sqlite3
from db import get_db

def migrate():
    """Add email notification columns to scheduled_tests table"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(scheduled_tests)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add notify_email column if it doesn't exist
        if 'notify_email' not in columns:
            cursor.execute("""
                ALTER TABLE scheduled_tests 
                ADD COLUMN notify_email TEXT
            """)
            print("✓ Added notify_email column")
        else:
            print("✓ notify_email column already exists")
        
        # Add notify_on_success column if it doesn't exist
        if 'notify_on_success' not in columns:
            cursor.execute("""
                ALTER TABLE scheduled_tests 
                ADD COLUMN notify_on_success INTEGER DEFAULT 0
            """)
            print("✓ Added notify_on_success column")
        else:
            print("✓ notify_on_success column already exists")
        
        # Add notify_on_failure column if it doesn't exist
        if 'notify_on_failure' not in columns:
            cursor.execute("""
                ALTER TABLE scheduled_tests 
                ADD COLUMN notify_on_failure INTEGER DEFAULT 0
            """)
            print("✓ Added notify_on_failure column")
        else:
            print("✓ notify_on_failure column already exists")
        
        # Add last_notification_sent column if it doesn't exist
        if 'last_notification_sent' not in columns:
            cursor.execute("""
                ALTER TABLE scheduled_tests 
                ADD COLUMN last_notification_sent TEXT
            """)
            print("✓ Added last_notification_sent column")
        else:
            print("✓ last_notification_sent column already exists")
        
        # Add last_notification_status column if it doesn't exist
        if 'last_notification_status' not in columns:
            cursor.execute("""
                ALTER TABLE scheduled_tests 
                ADD COLUMN last_notification_status TEXT
            """)
            print("✓ Added last_notification_status column")
        else:
            print("✓ last_notification_status column already exists")
        
        conn.commit()
        print("✓ Migration completed: Email notification columns added")
        
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("✓ Migration already applied")
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

