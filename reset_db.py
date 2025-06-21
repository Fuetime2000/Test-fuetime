"""
Script to completely reset the database by removing it and reinitializing.
This will delete ALL data in the database.
"""
import os
import sys
from pathlib import Path

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def reset_database():
    """Reset the database by removing the database file and reinitializing."""
    try:
        # Path to the database file
        db_path = Path('instance/fuetime.db')
        
        # Check if database exists
        if not db_path.exists():
            print("Database file not found at:", db_path.absolute())
            return False
            
        # Remove the database file
        os.remove(db_path)
        print(f"✓ Removed database file: {db_path.absolute()}")
        
        # Import app and db after removing the old database
        from app import app, db
        
        with app.app_context():
            # Drop all tables
            db.drop_all()
            print("✓ Dropped all tables")
            
            # Create all tables
            db.create_all()
            print("✓ Recreated database schema")
            
            # Commit the changes
            db.session.commit()
            print("\n✓ Database reset completed successfully!")
            return True
            
    except Exception as e:
        print(f"\n✗ Error resetting database: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("WARNING: This will delete ALL data in the database!")
    confirm = input("Are you sure you want to continue? (yes/no): ")
    
    if confirm.lower() == 'yes':
        print("\nResetting database...")
        if reset_database():
            print("\nPlease restart your Flask application to complete the reset.")
        else:
            print("\nDatabase reset failed. Check the error messages above.")
    else:
        print("Database reset cancelled.")
