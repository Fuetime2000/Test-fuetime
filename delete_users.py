from app import app, db, User, Review, Message, ContactRequest

def delete_all_users():
    with app.app_context():
        # Delete all users
        db.session.query(User).delete()
        
        # Reset related tables
        db.session.query(Review).delete()
        db.session.query(Message).delete()
        db.session.query(ContactRequest).delete()
        
        db.session.commit()
        print("All users and related data deleted.")

if __name__ == '__main__':
    delete_all_users()
