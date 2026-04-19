
import sqlite3

def check_and_add_column():
    try:
        conn = sqlite3.connect('sqlite.db')
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute('PRAGMA table_info(users)')
        columns = cursor.fetchall()
        
        print("Current columns in users table:")
        for col in columns:
            print(col)
            
        column_names = [col[1] for col in columns]
        
        if 'verification_status' not in column_names:
            print("\nAdding verification_status column...")
            cursor.execute('''
                ALTER TABLE users 
                ADD COLUMN verification_status TEXT DEFAULT 'pending'
            ''')
            conn.commit()
            print("Successfully added verification_status column")
            
            # Verify the change
            cursor.execute('PRAGMA table_info(users)')
            print("\nColumns after addition:")
            for col in cursor.fetchall():
                print(col)
        else:
            print("\nverification_status column already exists")
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"\nError: {e}")
        return False

if __name__ == "__main__":
    check_and_add_column()
