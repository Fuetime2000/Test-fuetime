import os
import sys
from app import create_app, db
from models import *  # Import all models to ensure tables are created
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import uuid

# Get absolute path to database file
db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fuetime.db')

# Delete existing database file
if os.path.exists(db_file):
    os.remove(db_file)
    print(f"Removed existing database: {db_file}")

def init_database():
    # Create app and push app context
    app = create_app()
    with app.app_context():
        try:
            # Create all tables
            print("Creating database tables...")
            db.create_all()
            
            # Check if admin user already exists
            admin = User.query.filter_by(email='admin@example.com').first()
            if not admin:
                print("Creating admin user...")
                # Create admin user with all required fields
                admin = User()
                admin.email = 'admin@example.com'
                admin.phone = '1234567890'
                admin.full_name = 'Admin User'
                admin.username = 'admin'  # Set a fixed username for admin
                admin.password_hash = generate_password_hash('admin123')
                admin.is_admin = True
                admin.work = 'Administrator'
                admin.experience = '5+ years'
                admin.education = 'Bachelor\'s Degree'
                admin.live_location = 'Main Office'
                admin.current_location = 'Main Office'
                admin.payment_type = 'Hourly'
                admin.payment_charge = 0.0
                admin.skills = 'Administration, Management'
                admin.categories = 'Administration'
                admin.is_online = False
                admin.last_active = datetime.utcnow()
                admin.email_verified = True
                admin.phone_verified = True
                admin.wallet_balance = 1000.0  # Give admin some initial balance
                
                db.session.add(admin)
                db.session.commit()
                print("Admin user created successfully")
            else:
                print("Admin user already exists")
            
            # Verify that all required tables exist
            inspector = db.inspect(db.engine)
            required_tables = ['users', 'calls', 'transactions']  # Add other required table names
            missing_tables = [table for table in required_tables if not inspector.has_table(table)]
            
            if missing_tables:
                print(f"Warning: The following tables are missing: {', '.join(missing_tables)}")
                print("Attempting to recreate all tables...")
                db.drop_all()
                db.create_all()
                print("All tables recreated")
            
            print("Database initialization completed successfully")
            return True
            
        except Exception as e:
            print(f"Error during database initialization: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False

if __name__ == "__main__":
    init_database()
