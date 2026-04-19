
import sqlite3

def fix_verification_status():
    try:
        conn = sqlite3.connect('sqlite.db')
        cursor = conn.cursor()
        
        # Update all records to use uppercase values
        print("Updating verification_status values to uppercase...")
        cursor.execute('''
            UPDATE users 
            SET verification_status = 'PENDING' 
            WHERE verification_status = 'pending'
        ''')
        conn.commit()
        
        print(f"Updated {cursor.rowcount} records")
        
        # Verify the change
        cursor.execute('SELECT DISTINCT verification_status FROM users')
        values = cursor.fetchall()
        print("\nDistinct verification_status values:")
        for value in values:
            print(value[0])
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"\nError: {e}")
        return False

if __name__ == "__main__":
    fix_verification_status()
