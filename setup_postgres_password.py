#!/usr/bin/env python3
"""
Script to set up PostgreSQL user password for Plotra Platform.
Run this script to configure the database connection.
"""
import os
import subprocess
import sys

def get_postgres_password():
    """Get password from config or prompt user"""
    # Try to read from config.yaml
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            content = f.read()
            # Look for password in config
            for line in content.split('\n'):
                if 'password:' in line.lower():
                    # Extract password value
                    parts = line.split('password:')
                    if len(parts) > 1:
                        password = parts[1].strip().strip('"').strip("'")
                        if password and password != '""' and password != "''":
                            return password
    
    return "postgres"  # Default

def setup_postgres():
    """Set up PostgreSQL user and database"""
    password = get_postgres_password()
    
    print(f"Configuring PostgreSQL for Plotra Platform...")
    print(f"Database name: plotra_db")
    print(f"Username: postgres")
    print(f"Password: {password}")
    print()
    
    # Commands to run in PostgreSQL
    commands = [
        # Set password for postgres user
        f"ALTER USER postgres WITH PASSWORD '{password}';",
        # Create database if not exists
        "CREATE DATABASE plotra_db;",
        # Grant all privileges
        "GRANT ALL PRIVILEGES ON DATABASE plotra_db TO postgres;",
    ]
    
    # Try to execute using psql
    try:
        # First, try to connect without password to set it
        print("Attempting to set PostgreSQL password...")
        
        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = 'postgres'  # Try default first
        
        # Try to create database and set password
        result = subprocess.run(
            ['psql', '-U', 'postgres', '-c', f"ALTER USER postgres WITH PASSWORD '{password}';"],
            capture_output=True,
            text=True,
            env=env
        )
        
        if result.returncode == 0:
            print("✓ Password updated successfully")
        else:
            print(f"Note: {result.stderr.strip()}")
            
        # Try to create database
        result = subprocess.run(
            ['psql', '-U', 'postgres', '-c', 'CREATE DATABASE plotra_db;'],
            capture_output=True,
            text=True,
            env={**env, 'PGPASSWORD': password}
        )
        
        if 'already exists' in result.stderr or result.returncode == 0:
            print("✓ Database 'plotra_db' ready")
        else:
            print(f"Database creation: {result.stderr.strip()}")
            
        print("\n✅ PostgreSQL setup complete!")
        print("\nYou can now start the server with:")
        print("  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
        
    except FileNotFoundError:
        print("""
ERROR: psql command not found.

Please install PostgreSQL and ensure it's in your PATH, or run these commands manually:

1. Connect to PostgreSQL:
   psql -U postgres

2. Set password:
   ALTER USER postgres WITH PASSWORD 'postgres';

3. Create database:
   CREATE DATABASE plotra_db;
   GRANT ALL PRIVILEGES ON DATABASE plotra_db TO postgres;

4. Enable PostGIS extension (if needed):
   psql -U postgres -d plotra_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
""")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_postgres()
