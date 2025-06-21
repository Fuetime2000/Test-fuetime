"""
Script to reset the database by removing all users and related data.
Run this script with: python reset_database.py
"""
import os
import sys
from pathlib import Path

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Now import the app and models
from app import create_app, db
from models.user import User
from models.message import Message
from models.review import Review
from models.contact_request import ContactRequest
from models.user_interaction import UserInteraction

# Create app with the correct config
app = create_app()

def reset_database():
    """Delete all users and related data from the database."""
    with app.app_context():
        try:
            print("Starting database reset...")
            print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            # Verify database exists
            db_file = Path('instance/fuetime.db')
            if not db_file.exists():
                print("Error: Database file not found at", db_file.absolute())
                return
                
            print("Database file exists. Proceeding with reset...")
            
            # Delete all messages
            Message.query.delete()
            print("✓ Deleted all messages.")
            
            # Delete all reviews
            Review.query.delete()
            print("✓ Deleted all reviews.")
            
            # Delete all contact requests
            ContactRequest.query.delete()
            print("✓ Deleted all contact requests.")
            
            # Delete all user interactions
            UserInteraction.query.delete()
            print("✓ Deleted all user interactions.")
            
            # Delete all users
            user_count = User.query.count()
            User.query.delete()
            print(f"✓ Deleted all users ({user_count} users removed).")
            
            # Commit all changes
            db.session.commit()
            print("\n✓ Database reset completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error resetting database: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    reset_database()
