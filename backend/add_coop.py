import sqlite3
import uuid

# Connect to the database
conn = sqlite3.connect('backend/sqlite.db')
cursor = conn.cursor()

# Check current state
cursor.execute('SELECT COUNT(*) FROM cooperatives')
count = cursor.fetchone()[0]
print(f'Current cooperative count: {count}')

# Insert a cooperative
coop_id = str(uuid.uuid4())
sql = '''INSERT INTO cooperatives (id, name, code, created_at, updated_at, is_active, verification_status, country) 
         VALUES (?, ?, ?, datetime('now'), datetime('now'), 1, 'verified', 'Kenya')'''

try:
    cursor.execute(sql, (coop_id, 'Nyeri Coffee Farmers Cooperative', 'NKY001'))
    conn.commit()
    print(f'Inserted cooperative: {coop_id}')
except Exception as e:
    print(f'Insert error: {e}')

# Verify
cursor.execute('SELECT id, name, code FROM cooperatives')
rows = cursor.fetchall()
print(f'Cooperatives after insert: {len(rows)}')
for row in rows:
    print(f'  - {row}')

conn.close()
