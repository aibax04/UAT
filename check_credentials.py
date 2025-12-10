import sqlite3

conn = sqlite3.connect("uat.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM credentials")
print(cursor.fetchall())

