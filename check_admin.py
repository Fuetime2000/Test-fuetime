from app import app, db, User
import os

with app.app_context():
    # Get all admin users
    admins = User.query.filter_by(is_admin=True).all()
    
    if not admins:
        print("No admin users found in the database.")
    else:
        print(f"Found {len(admins)} admin users:")
        for admin in admins:
            print(f"\nAdmin: {admin.full_name} ({admin.email})")
            print(f"Photo path in DB: {admin.photo}")
            
            if admin.photo:
                # Check in profile_pics directory
                photo_path = os.path.join(app.root_path, 'static', 'uploads', 'profile_pics', admin.photo)
                print(f"Looking for photo at: {photo_path}")
                print(f"Photo exists: {os.path.exists(photo_path)}")
                
                # Check in root uploads directory
                alt_photo_path = os.path.join(app.root_path, 'static', 'uploads', admin.photo)
                if os.path.exists(alt_photo_path):
                    print(f"Found photo at alternative location: {alt_photo_path}")
                    # Update the photo path in the database
                    admin.photo = admin.photo  # This will trigger the setter if there is one
                    db.session.commit()
                    print("Updated photo path in database")
            else:
                print("No photo path set for this admin user.")
    
    # Also check the default admin email
    admin_email = 'admin@fuetime.com'
    admin = User.query.filter_by(email=admin_email).first()
    if admin:
        print(f"\nFound user with email {admin_email}:")
        print(f"Is admin: {admin.is_admin}")
        print(f"Photo path: {admin.photo}")
    else:
        print(f"\nNo user found with email {admin_email}")
