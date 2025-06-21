from app import app, db
from models.project import Technology

# List of common technologies
technologies = [
    'Python', 'JavaScript', 'HTML', 'CSS', 'React', 'Vue.js', 'Angular',
    'Node.js', 'Flask', 'Django', 'PostgreSQL', 'MySQL', 'MongoDB',
    'Redis', 'Docker', 'Kubernetes', 'AWS', 'Azure', 'GCP',
    'Git', 'CI/CD', 'RESTful APIs', 'GraphQL', 'TypeScript',
    'Java', 'Spring Boot', 'C#', '.NET', 'PHP', 'Laravel'
]

def add_technologies():
    with app.app_context():
        # Add technologies if they don't exist
        for tech_name in technologies:
            if not Technology.query.filter_by(name=tech_name).first():
                tech = Technology(name=tech_name)
                db.session.add(tech)
        
        db.session.commit()
        print("Technologies added successfully!")

if __name__ == '__main__':
    add_technologies()
