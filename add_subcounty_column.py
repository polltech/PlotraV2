#!/usr/bin/env python3
"""
Script to add subcounty column to existing database tables.
Run this script to update your database with the new subcounty field.

Supports both SQLite and PostgreSQL databases.
"""

import os
import sys

def add_subcounty_column_sqlite(db_path):
    """Add subcounty column to users table in SQLite."""
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return False
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists in users table
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'subcounty' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN subcounty VARCHAR(100)")
            conn.commit()
            print(f"OK - Added 'subcounty' column to users table in {db_path}")
        else:
            print(f"OK - 'subcounty' column already exists in users table ({db_path})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error updating SQLite database {db_path}: {e}")
        return False

def add_subcounty_column_postgres():
    """Add subcounty column to users table in PostgreSQL."""
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed. Installing...")
        os.system(f"{sys.executable} -m pip install psycopg2-binary")
        import psycopg2
    
    # Try different connection methods
    connection_attempts = [
        # Try docker host first (localhost)
        {"host": "localhost", "port": "5432", "user": "postgres", "password": "postgres", "dbname": "plotra_db"},
        {"host": "localhost", "port": "5432", "user": "postgres", "password": "postgres", "dbname": "postgres"},
        # Try docker container name
        {"host": "plotra-postgres", "port": "5432", "user": "postgres", "password": "postgres", "dbname": "plotra_db"},
        # Try without password
        {"host": "localhost", "port": "5432", "user": "postgres", "password": "", "dbname": "plotra_db"},
    ]
    
    for attempt in connection_attempts:
        try:
            print(f"Trying: host={attempt['host']}, dbname={attempt['dbname']}...")
            conn = psycopg2.connect(**attempt)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'subcounty'
            """)
            result = cursor.fetchone()
            
            if result is None:
                cursor.execute("ALTER TABLE users ADD COLUMN subcounty VARCHAR(100)")
                conn.commit()
                print(f"OK - Added 'subcounty' column to users table")
            else:
                print(f"OK - 'subcounty' column already exists in users table")
            
            cursor.close()
            conn.close()
            return True
            
        except psycopg2.OperationalError as e:
            print(f"  Failed: {e}")
            continue
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    print("All connection attempts failed.")
    return False

if __name__ == "__main__":
    print("Checking for databases and adding subcounty column...\n")
    
    # Try SQLite databases first
    sqlite_dbs = ["plotra_data.db", "sqlite.db", "app/plotra.db", "backend/sqlite.db"]
    
    sqlite_updated = False
    for db in sqlite_dbs:
        if os.path.exists(db):
            print(f"Found SQLite database: {db}")
            if add_subcounty_column_sqlite(db):
                sqlite_updated = True
    
    if sqlite_updated:
        print("\nOK - SQLite database(s) updated!")
    else:
        print("No SQLite databases found or already updated.")
    
    # Try PostgreSQL
    print("\nTrying PostgreSQL...")
    postgres_updated = add_subcounty_column_postgres()
    
    if postgres_updated:
        print("OK - PostgreSQL database updated!")
    
    print("\nDone!")
