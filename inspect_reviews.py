from app import app, db
from models.review import Review

def check_reviews():
    with app.app_context():
        # Get all reviews
        all_reviews = Review.query.all()
        print(f"Total reviews in database: {len(all_reviews)}")
        
        # Get all users who have reviews
        from sqlalchemy import distinct
        user_ids = db.session.query(distinct(Review.worker_id)).all()
        print(f"Users with reviews: {[uid[0] for uid in user_ids] if user_ids else 'None'}")
        
        # Check reviews for user with ID 3 (from the URL)
        user_id = 3  # Change this to the user ID you're checking
        user_reviews = Review.query.filter_by(worker_id=user_id).all()
        print(f"\nReviews for user {user_id}:")
        
        if not user_reviews:
            print("No reviews found for this user")
            # Check if user exists
            from models.user import User
            user = User.query.get(user_id)
            if not user:
                print(f"ERROR: User with ID {user_id} does not exist")
            return
            
        for i, review in enumerate(user_reviews, 1):
            print(f"\nReview {i}:")
            print(f"  ID: {review.id}")
            print(f"  Worker ID: {review.worker_id}")
            print(f"  Reviewer ID: {review.reviewer_id}")
            print(f"  Rating: {review.rating}")
            print(f"  Comment: {review.comment}")
            print(f"  Created at: {review.created_at}")
            
            # Try to get reviewer info
            if hasattr(review, 'reviewer'):
                print(f"  Reviewer: {review.reviewer.full_name if review.reviewer else 'None'}")
            else:
                print("  No reviewer relationship found")

if __name__ == '__main__':
    check_reviews()
