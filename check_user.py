from app import app, db, User

with app.app_context():
    user = User.query.filter_by(phone='1234567890').first()
    if user:
        print(f'Found existing user with phone 1234567890: {user.email}')
