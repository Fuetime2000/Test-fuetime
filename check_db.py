from app import app, db, User

with app.app_context():
    # Get all users
    users = User.query.all()
    print(f"\nTotal users in database: {len(users)}")

    if users:
        print("\nSample users:")
        for user in users[:5]:  # Show first 5 users
            print(f"ID: {user.id}, Name: {user.full_name}, Skills: {user.skills}, Active: {user.active}")
    else:
        print("\nNo users found in database!")

    # Check active users
    active_users = User.query.filter_by(active=True).all()
    print(f"\nTotal active users: {len(active_users)}")

    # Check if there are any users with 'dipendra' in their name or skills
    test_search = User.query.filter(
        db.or_(
            User.full_name.ilike('%dipendra%'),
            User.skills.ilike('%dipendra%'),
            User.work.ilike('%dipendra%')
        )
    ).all()
    print(f"\nUsers matching 'dipendra': {len(test_search)}")
