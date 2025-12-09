import sqlite3

# Connect to database
conn = sqlite3.connect("uat.db")
cursor = conn.cursor()

# Delete any existing nexusai credentials
cursor.execute("DELETE FROM credentials WHERE app_name = 'nexusai'")


cursor.execute("""
INSERT INTO credentials (app_name, login_url, username, password)
VALUES (?, ?, ?, ?)
""", (
    "nexusai",
    "https://nexusai-ndus.onrender.com/login?next=%2F",
    "aibad",
    "1234"
))

conn.commit()
conn.close()

print("✓ NexusAI credentials added successfully!")
print("\nCredentials stored:")
print("  App: nexusai")
print("  URL: https://nexusai-ndus.onrender.com/login?next=%2F")
print("  Username: aibad")
print("  Password: ****")
print("\nYou can now run: python main.py")