from app import app, db, User
from werkzeug.security import generate_password_hash
from datetime import datetime

with app.app_context():
    # Create all tables
    db.create_all()
    
    # Check if admin user exists
    admin = User.query.filter_by(email='admin@fuetime.com').first()
    if not admin:
        # Create admin user
        admin = User(
            email='admin@fuetime.com',
            phone='9999999999',
            full_name='Admin User',
            username='admin_user',
            is_admin=True,
            password_hash=generate_password_hash('admin123'),
            created_at=datetime.utcnow(),
            photo=None,  # No profile image for admin
            last_active=datetime.utcnow(),
            is_online=False,
            active=True,
            authenticated=True,
            age=30,  # Add a default age
            availability='available'
        )
        db.session.add(admin)
        db.session.commit()
        print(f'Created admin user with email: {admin.email} and password: admin123')
    else:
        # Make existing user admin
        admin.is_admin = True
        db.session.commit()
        print(f'Updated {admin.email} to admin')
