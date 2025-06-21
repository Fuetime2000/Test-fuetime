from flask import Blueprint, render_template, abort
from datetime import datetime

blog = Blueprint('blog', __name__)

# Sample blog posts data
blog_posts = {
    'freelancing-tips': {
        'title': 'Top Freelancing Tips for 2025',
        'date': datetime(2025, 5, 20),
        'read_time': 5,
        'image_url': '/static/images/blog/freelancing-tips.jpg',
        'content': '''
            <p class="lead">The freelancing landscape is constantly evolving. Here are the top tips to succeed in 2025.</p>
            <h2>1. Master Your Niche</h2>
            <p>Specialization is more important than ever. Focus on becoming an expert in your field rather than a jack-of-all-trades.</p>
            <h2>2. Embrace AI Tools</h2>
            <p>Artificial Intelligence is here to stay. Learn to leverage AI tools to enhance your productivity and deliver better results.</p>
            <h2>3. Build Your Personal Brand</h2>
            <p>Your online presence is your portfolio. Invest time in creating a strong personal brand that attracts high-quality clients.</p>
        ''',
        'author': 'Sarah Johnson',
        'author_image': '/static/images/authors/sarah.jpg',
        'author_bio': 'Freelance Success Coach with 10+ years of experience'
    },
    'remote-work-guide': {
        'title': 'Remote Work Success Guide',
        'date': datetime(2025, 5, 15),
        'read_time': 6,
        'image_url': '/static/images/blog/remote-work.jpg',
        'content': '''
            <p class="lead">Master the art of remote work with these proven strategies.</p>
            <h2>Create a Dedicated Workspace</h2>
            <p>Having a designated work area helps maintain work-life balance and boosts productivity.</p>
            <h2>Establish a Routine</h2>
            <p>Structure your day like you would in an office. Set clear working hours and stick to them.</p>
            <h2>Stay Connected</h2>
            <p>Use collaboration tools effectively to maintain strong communication with your team and clients.</p>
        ''',
        'author': 'Michael Chen',
        'author_image': '/static/images/authors/michael.jpg',
        'author_bio': 'Remote Work Consultant & Digital Nomad'
    },
    'digital-marketing': {
        'title': 'Digital Marketing Essentials',
        'date': datetime(2025, 5, 10),
        'read_time': 7,
        'image_url': '/static/images/blog/digital-marketing.jpg',
        'content': '''
            <p class="lead">Master the fundamentals of digital marketing to grow your online presence.</p>
            <h2>Content is King</h2>
            <p>Create valuable, engaging content that resonates with your target audience.</p>
            <h2>SEO Fundamentals</h2>
            <p>Learn the basics of search engine optimization to improve your visibility.</p>
            <h2>Social Media Strategy</h2>
            <p>Develop a consistent social media presence across relevant platforms.</p>
        ''',
        'author': 'Emily Rodriguez',
        'author_image': '/static/images/authors/emily.jpg',
        'author_bio': 'Digital Marketing Strategist'
    },
    'skill-development': {
        'title': 'Skill Development Guide',
        'date': datetime(2025, 5, 5),
        'read_time': 5,
        'image_url': '/static/images/blog/skill-development.jpg',
        'content': '''
            <p class="lead">A comprehensive guide to continuous learning and skill development.</p>
            <h2>Set Clear Goals</h2>
            <p>Define specific, measurable objectives for your skill development journey.</p>
            <h2>Practice Deliberately</h2>
            <p>Focus on quality practice sessions rather than quantity.</p>
            <h2>Seek Feedback</h2>
            <p>Regular feedback is crucial for improvement and growth.</p>
        ''',
        'author': 'David Kim',
        'author_image': '/static/images/authors/david.jpg',
        'author_bio': 'Learning & Development Expert'
    },
    'networking-tips': {
        'title': 'Professional Networking Tips',
        'date': datetime(2025, 5, 1),
        'read_time': 4,
        'image_url': '/static/images/blog/networking.jpg',
        'content': '''
            <p class="lead">Build and maintain a strong professional network with these proven strategies.</p>
            <h2>Quality Over Quantity</h2>
            <p>Focus on building meaningful connections rather than collecting contacts.</p>
            <h2>Give Before You Take</h2>
            <p>Offer value to your network before asking for favors.</p>
            <h2>Stay Active Online</h2>
            <p>Regularly engage with your network on professional platforms.</p>
        ''',
        'author': 'Lisa Thompson',
        'author_image': '/static/images/authors/lisa.jpg',
        'author_bio': 'Professional Networking Coach'
    }
}

@blog.route('/<slug>')
def post(slug):
    post = blog_posts.get(slug)
    if not post:
        abort(404)
    return render_template('blog/post.html', post=post)
