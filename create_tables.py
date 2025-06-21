from app import app, db
# Import all models to ensure tables are created
from models import User, Transaction, Subscription, Call
from datetime import datetime, timedelta
import uuid
from werkzeug.security import generate_password_hash

# Import other models as needed

def create_tables():
    with app.app_context():
        try:
            # Drop all tables first to avoid conflicts
            db.drop_all()
            # Create all tables
            db.create_all()
            print("All tables created successfully!")
            
            # Create a test user if it doesn't exist
            test_user1 = User.query.filter_by(email='test1@example.com').first()
            if not test_user1:
                test_user1 = User(
                    username='testuser1',
                    email='test1@example.com',
                    password_hash=generate_password_hash('testpassword'),
                    user_type='worker',
                    full_name='Test User1',
                    phone='1234567890',
                    wallet_balance=100.0,
                    email_verified=True,
                    phone_verified=True,
                    is_online=True
                )
                db.session.add(test_user1)
                db.session.commit()
                print("Created test user 1")
            
            test_user2 = User.query.filter_by(email='test2@example.com').first()
            if not test_user2:
                test_user2 = User(
                    username='testuser2',
                    email='test2@example.com',
                    password_hash=generate_password_hash('testpassword'),
                    user_type='client',
                    full_name='Test User2',
                    phone='9876543210',
                    wallet_balance=100.0,
                    email_verified=True,
                    phone_verified=True,
                    is_online=True
                )
                db.session.add(test_user2)
                db.session.commit()
                print("Created test user 2")
            
            # Add a test call record if needed
            try:
                call_id = f'call_{uuid.uuid4().hex}'
                
                # Create the call record
                test_call = Call(
                    call_id=call_id,
                    caller_id=test_user1.id,
                    callee_id=test_user2.id,
                    status='completed',
                    duration=60,  # 1 minute
                    cost=10.0  # Example cost in INR
                )
                db.session.add(test_call)
                
                # Refresh the users to get the latest data
                db.session.refresh(test_user1)
                db.session.refresh(test_user2)
                
                # Add a test transaction for the call
                transaction = Transaction(
                    user_id=test_user1.id,
                    amount=10.0,
                    description=f'Call to {test_user2.username} (1 min)',
                    transaction_type='debit',
                    status='completed',
                    reference_id=call_id,
                    metadata={
                        'call_id': call_id,
                        'duration_seconds': 60,
                        'rate_per_minute': 10.0,
                        'caller_id': test_user1.id,
                        'callee_id': test_user2.id,
                        'call_status': 'completed',
                        'call_timestamp': datetime.utcnow().isoformat()
                    }
                )
                db.session.add(transaction)
                
                # Update user wallet balances
                test_user1.wallet_balance = float(test_user1.wallet_balance or 0) - 10.0
                
                # Commit all changes
                db.session.commit()
                print("Test call and transaction records added successfully!")
                print(f"Call ID: {call_id}")
                print(f"Caller ID: {test_user1.id}, New Balance: {test_user1.wallet_balance}")
                print(f"Callee ID: {test_user2.id}")
                
            except Exception as e:
                db.session.rollback()
                print(f"Error adding test call record: {str(e)}")
                import traceback
                traceback.print_exc()
                raise  # Re-raise the exception to see the full traceback
                
        except Exception as e:
            print(f"Error creating tables: {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_tables()
