# Import all models to ensure they are registered with SQLAlchemy
from .base import db
from .user import User
from .portfolio import Portfolio, PortfolioProject, ProjectTechnology, PortfolioSkill, PortfolioRating
from .message import Message
from .transaction import Transaction
from .contact_request import ContactRequest
from .subscription import Subscription
from .Call import Call
from .review import Review
from .donation import Donation
from .behavior_tracking import UserBehavior, FraudAlert
from .project import Project, Technology
from .help_request import HelpRequest
from .user_interaction import UserInteraction

# Create a dictionary of all models for easy access
models = {
    'User': User,
    'Portfolio': Portfolio,
    'PortfolioProject': PortfolioProject,
    'ProjectTechnology': ProjectTechnology,
    'PortfolioSkill': PortfolioSkill,
    'Message': Message,
    'Transaction': Transaction,
    'ContactRequest': ContactRequest,
    'Subscription': Subscription,
    'Call': Call,
    'Review': Review,
    'Donation': Donation,
    'UserBehavior': UserBehavior,
    'FraudAlert': FraudAlert,
    'Project': Project,
    'Technology': Technology,
    'PortfolioRating': PortfolioRating,
    'HelpRequest': HelpRequest,
    'UserInteraction': UserInteraction
}

# Make all models available when importing from models
__all__ = list(models.keys()) + ['db']
