import os
from app import app, db, User

with app.app_context():
    admin = User.query.filter_by(is_admin=True).first()
    if admin:
        print(f"Admin email: {admin.email}")
        print(f"Photo path: {admin.photo}")
        
        # Check if photo exists in profile_pics directory
        if admin.photo:
            photo_path = os.path.join(app.root_path, 'static', 'uploads', 'profile_pics', admin.photo)
            print(f"Full photo path: {photo_path}")
            print(f"Photo exists: {os.path.exists(photo_path)}")
            
            # Also check in the root uploads directory
            alt_photo_path = os.path.join(app.root_path, 'static', 'uploads', admin.photo)
            if os.path.exists(alt_photo_path):
                print(f"Found photo in alternative location: {alt_photo_path}")
                # Update the photo path in the database
                admin.photo = admin.photo  # This will trigger the setter if there is one
                db.session.commit()
                print("Updated photo path in database")
    else:
        print("No admin user found")
