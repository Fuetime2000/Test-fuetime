from app import app, db
from models.user import User

def fix_admin_user():
    with app.app_context():
        # Find the admin user by email
        admin_email = 'admin@fuetime.com'  # Update this if your admin email is different
        admin = User.query.filter_by(email=admin_email, is_admin=True).first()
        
        if admin:
            print(f"Found admin user: {admin.email}")
            if not admin.email_verified:
                admin.email_verified = True
                db.session.commit()
                print("Admin email verification status updated to True")
            else:
                print("Admin email is already verified")
        else:
            print(f"No admin user found with email: {admin_email}")

if __name__ == '__main__':
    fix_admin_user()
