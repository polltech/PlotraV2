#!/usr/bin/env python3
"""
Script to add an admin user to the Plotra database.
"""
import sqlite3
import hashlib
import secrets

def hash_password(password):
    """Hash password using SHA256 with salt (matching simple_api.py format)"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def main():
    conn = sqlite3.connect('plotra_data.db')
    cursor = conn.cursor()
    
    # Check if admin@plotra.africa already exists
    cursor.execute('SELECT id FROM users WHERE email = ?', ('admin@plotra.africa',))
    if cursor.fetchone():
        print('Admin user admin@plotra.africa already exists')
    else:
        password_hash = hash_password('password123')
        print(f'Password hash: {password_hash}')
        
        cursor.execute('''
            INSERT INTO users (email, password_hash, first_name, last_name, role, region, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('admin@plotra.africa', password_hash, 'Admin', 'User', 'platform_admin', 'Nairobi', 'active'))
        
        print('Created admin user: admin@plotra.africa with password: password123')
    
    conn.commit()
    
    # Verify
    cursor.execute('SELECT id, email, role FROM users')
    print('\nAll users in database:')
    for user in cursor.fetchall():
        print(f'  ID: {user[0]}, Email: {user[1]}, Role: {user[2]}')
    
    conn.close()
    print('\nDone!')

if __name__ == '__main__':
    main()
