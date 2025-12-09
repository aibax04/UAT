import sqlite3

DB_PATH = "uat.db"

def get_db():
    return sqlite3.connect(DB_PATH)
