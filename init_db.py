import sqlite3

with open("schema.sql", "r") as f:
    schema = f.read()

conn = sqlite3.connect("uat.db")
cursor = conn.cursor()
cursor.executescript(schema)
conn.commit()
conn.close()

print("SQLite database initialized successfully!")
