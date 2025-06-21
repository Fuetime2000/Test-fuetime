from app import app, db
from models.review import Review
from models.user import User

def check_reviews():
    with app.app_context():
        # Get total number of reviews
        total_reviews = Review.query.count()
        print(f"Total reviews in database: {total_reviews}")
        
        # Get all users who have reviews
        users_with_reviews = db.session.query(Review.worker_id).distinct().all()
        print(f"Users with reviews: {[u[0] for u in users_with_reviews]}")
        
        # Check reviews for user with ID 3 (from the URL)
        user_id = 3
        user_reviews = Review.query.filter_by(worker_id=user_id).all()
        print(f"\nReviews for user {user_id}:")
        for i, review in enumerate(user_reviews, 1):
            print(f"\nReview {i}:")
            print(f"  ID: {review.id}")
            print(f"  Rating: {review.rating}")
            print(f"  Comment: {review.comment}")
            print(f"  Created at: {review.created_at}")
            
            # Try to get reviewer info
            if hasattr(review, 'reviewer'):
                print(f"  Reviewer: {review.reviewer.full_name if review.reviewer else 'None'}")
            else:
                print("  No reviewer relationship found")
                
                # Try to get reviewer manually
                from sqlalchemy.orm import joinedload
                full_review = Review.query.options(joinedload(Review.reviewer)).get(review.id)
                if hasattr(full_review, 'reviewer') and full_review.reviewer:
                    print(f"  Reviewer (manual load): {full_review.reviewer.full_name}")
                else:
                    print("  Could not load reviewer info")

if __name__ == '__main__':
    check_reviews()
