# Fix user roles in SQLite database
import sqlite3

conn = sqlite3.connect('backend/sqlite.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get all users
cur.execute('SELECT id, email, role FROM users')
users = cur.fetchall()

print(f"Found {len(users)} users")

for user in users:
    old_role = user['role']
    new_role = None
    
    # Map old roles to new lowercase roles
    if old_role == 'FARMER':
        new_role = 'farmer'
    elif old_role == 'COOPERATIVE_OFFICER':
        new_role = 'cooperative_officer'
    elif old_role == 'KIPAWA_ADMIN':
        new_role = 'plotra_admin'
    elif old_role == 'EUDR_REVIEWER':
        new_role = 'eudr_reviewer'
    elif old_role == 'KIPACA_ADMIN':  # typo variant
        new_role = 'plotra_admin'
    elif old_role == 'SUPER_ADMIN':
        new_role = 'super_admin'
    elif old_role == 'PLATFORM_ADMIN':
        new_role = 'platform_admin'
    
    if new_role and new_role != old_role:
        print(f"Updating {user['email']}: {old_role} -> {new_role}")
        cur.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user['id']))

conn.commit()

# Verify
cur.execute('SELECT DISTINCT role FROM users')
print("\nNew roles in database:")
for row in cur.fetchall():
    print(f"  {row[0]}")

conn.close()
print("\nDone!")