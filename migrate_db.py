import sqlite3

def migrate_database():
    """Add missing columns to existing database"""
    conn = sqlite3.connect("uat.db")
    cursor = conn.cursor()
    
    try:
        # Check if enhanced_data column exists in reports table
        cursor.execute("PRAGMA table_info(reports)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'enhanced_data' not in columns:
            print("Adding enhanced_data column to reports table...")
            cursor.execute("ALTER TABLE reports ADD COLUMN enhanced_data TEXT")
            conn.commit()
            print("✓ Migration complete: enhanced_data column added")
        else:
            print("✓ Database already has enhanced_data column")
            
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()

