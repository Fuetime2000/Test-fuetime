from app import app, db, User
import os

with app.app_context():
    # Get the admin user
    admin = User.query.filter_by(email='admin@fuetime.com').first()
    
    if admin:
        print(f"Found admin user: {admin.email}")
        print(f"Current photo path: {admin.photo}")
        
        # Update the photo path to just the filename
        if admin.photo and '/' in admin.photo:
            # Extract just the filename
            new_photo = os.path.basename(admin.photo)
            print(f"Updating photo path to: {new_photo}")
            admin.photo = new_photo
            db.session.commit()
            print("Updated admin user's photo path in the database")
        else:
            # Set a default admin icon
            admin.photo = 'admin_icon.png'
            db.session.commit()
            print("Set default admin icon")
    else:
        print("Admin user not found")
