# app.py

import os
import logging
import urllib.parse
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import random
import base64
import io
from PIL import Image
import user_agents

# Initialize Flask
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Replace with a secure key in production

# Database configuration
server = os.environ.get('AZURE_SQL_SERVER', 'your_server.database.windows.net')
database = os.environ.get('AZURE_SQL_DATABASE', 'your_database')
username = os.environ.get('AZURE_SQL_USER', 'your_username')
password = os.environ.get('AZURE_SQL_PASSWORD', 'your_password')
driver = '{ODBC Driver 17 for SQL Server}'

# Build the SQLAlchemy database URI
connection_string = (
    f"mssql+pyodbc://{username}:{password}@{server}/{database}"
    f"?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
)

app.config['SQLALCHEMY_DATABASE_URI'] = connection_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Flask-Session
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY'] = SQLAlchemy(app)
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
Session(app)

# Initialize Flask-SocketIO
socketio = SocketIO(app, async_mode='eventlet')

# Initialize Flask-SQLAlchemy
db = app.config['SESSION_SQLALCHEMY']

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Models
class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.Text, nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CrawlerVisit(db.Model):
    __tablename__ = 'crawler_visits'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100))
    user_agent = db.Column(db.String(500))
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    path = db.Column(db.String(200))
    is_crawler = db.Column(db.Boolean, default=False)
    crawler_name = db.Column(db.String(200))
    bot_confidence = db.Column(db.Integer)      # Confidence score (0-100)
    time_on_page = db.Column(db.Integer)        # Time spent in seconds
    scroll_depth = db.Column(db.Integer)        # Percentage scrolled

# Create all tables
with app.app_context():
    db.create_all()

# Constants
POSTS_PER_PAGE = 5  # Number of posts to load per scroll

# Helper Functions
def generate_random_image():
    """Generate a random colored image with base64 encoding"""
    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img = Image.new('RGB', (400, 300), color)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def create_sample_posts():
    """Create sample blog posts if none exist"""
    try:
        post_count = BlogPost.query.count()
        if post_count == 0:
            # Sample blog post data
            posts_data = [
                {
                    "title": "Understanding Web Crawlers",
                    "content": """Web crawlers, also known as spiders or bots, are automated programs that 
                    systematically browse the World Wide Web.""",
                    "slug": "understanding-web-crawlers"
                },
                {
                    "title": "SEO Best Practices 2024",
                    "content": """Search Engine Optimization remains a critical aspect of web development.""",
                    "slug": "seo-best-practices-2024"
                },
                {
                    "title": "Bot Detection Techniques",
                    "content": """Modern websites need sophisticated bot detection methods.""",
                    "slug": "bot-detection-techniques"
                }
            ]
            
            for post_data in posts_data:
                post = BlogPost(
                    title=post_data["title"],
                    content=post_data["content"],
                    image=generate_random_image(),
                    slug=post_data["slug"]
                )
                db.session.add(post)
            db.session.commit()
            logger.info("Sample posts created successfully")
    except Exception as e:
        logger.error(f"Error creating sample posts: {str(e)}")

def log_visit(request, path, time_on_page=None, scroll_depth=None):
    """Log visitor information with enhanced bot detection"""
    try:
        user_agent_string = request.headers.get('User-Agent', '')
        ip_address = request.remote_addr
        user_agent_parsed = user_agents.parse(user_agent_string)
        
        # Enhanced bot detection logic
        is_crawler = False
        crawler_name = None
        bot_confidence = 0
        
        known_bots = [
            'googlebot', 'bingbot', 'slurp', 'duckduckbot', 'baiduspider', 
            'yandexbot', 'sogou', 'exabot', 'facebot', 'ia_archiver'
        ]
        user_agent_lower = user_agent_string.lower()
        
        for bot in known_bots:
            if bot in user_agent_lower:
                is_crawler = True
                crawler_name = bot.capitalize()
                bot_confidence = 100
                break
        
        # Check if JavaScript is enabled
        js_enabled = request.cookies.get('js_enabled') == 'true'
        if not is_crawler and not js_enabled:
            # Possible bot
            bot_confidence += 50  # Adjust based on confidence levels
        
        # Assign a final confidence score
        if is_crawler:
            bot_confidence = 100
        elif not js_enabled:
            bot_confidence = min(bot_confidence, 80)  # Cap confidence
        else:
            bot_confidence = 0
        
        is_crawler_final = bot_confidence >= 80
        
        visit = CrawlerVisit(
            session_id=session.get('session_id', 'unknown'),
            user_agent=user_agent_string,
            ip_address=ip_address,
            path=path,
            is_crawler=is_crawler_final,
            crawler_name=crawler_name,
            bot_confidence=bot_confidence,
            time_on_page=time_on_page,
            scroll_depth=scroll_depth
        )
        db.session.add(visit)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error logging visit: {str(e)}")

# Routes
@app.route('/')
def home():
    try:
        create_sample_posts()
        
        log_visit(request, '/')
        posts_query = BlogPost.query.order_by(BlogPost.created_at.desc())
        total_posts = posts_query.count()
        posts = posts_query.limit(POSTS_PER_PAGE).all()
        has_more = total_posts > POSTS_PER_PAGE
        return render_template('home.html', posts=posts, has_more=has_more, next_page=2)
    except Exception as e:
        logger.error(f"Error in home route: {str(e)}")
        return str(e), 500

@app.route('/post/<slug>')
def post(slug):
    try:
        post = BlogPost.query.filter_by(slug=slug).first()
        if not post:
            return "Post not found", 404
        
        log_visit(request, f'/post/{slug}')
        
        # Get related posts
        related_posts = BlogPost.query.filter(BlogPost.slug != slug).order_by(func.random()).limit(3).all()
        
        return render_template('post.html', post=post, related_posts=related_posts)
    except Exception as e:
        logger.error(f"Error in post route: {str(e)}")
        return str(e), 500

@app.route('/admin')
def admin():
    try:
        # Get crawler statistics
        total_visits = CrawlerVisit.query.count()
        crawler_visits = CrawlerVisit.query.filter_by(is_crawler=True).count()
        human_visits = total_visits - crawler_visits
        
        # Get top crawlers
        top_crawlers = db.session.query(
            CrawlerVisit.crawler_name,
            func.count(CrawlerVisit.id).label('visit_count')
        ).filter(
            CrawlerVisit.is_crawler == True
        ).group_by(
            CrawlerVisit.crawler_name
        ).order_by(
            desc('visit_count')
        ).limit(10).all()
        
        stats = {
            'total_visits': total_visits,
            'crawler_visits': crawler_visits,
            'human_visits': human_visits,
            'top_crawlers': top_crawlers
        }
        
        return render_template('admin.html', stats=stats)
    except Exception as e:
        logger.error(f"Error in admin route: {str(e)}")
        return str(e), 500

@app.route('/analytics')
def analytics():
    try:
        days = request.args.get('days', 7, type=int)
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        total_visits = CrawlerVisit.query.filter(CrawlerVisit.timestamp >= cutoff).count()
        crawler_visits = CrawlerVisit.query.filter(
            CrawlerVisit.is_crawler == True,
            CrawlerVisit.timestamp >= cutoff
        ).count()
        human_visits = total_visits - crawler_visits
        
        top_crawlers = db.session.query(
            CrawlerVisit.crawler_name,
            func.count(CrawlerVisit.id).label('visit_count')
        ).filter(
            CrawlerVisit.is_crawler == True,
            CrawlerVisit.timestamp >= cutoff
        ).group_by(
            CrawlerVisit.crawler_name
        ).order_by(
            desc('visit_count')
        ).limit(10).all()
        
        # Device distribution (Simplified for demonstration)
        devices = db.session.query(
            func.case([
                (CrawlerVisit.user_agent.like('%Mobile%'), 'Mobile'),
                (CrawlerVisit.user_agent.like('%Tablet%'), 'Tablet'),
            ], else_='Desktop').label('device_type'),
            func.count(CrawlerVisit.id).label('count')
        ).filter(
            CrawlerVisit.timestamp >= cutoff
        ).group_by('device_type').all()
        
        # Time-on-page metrics
        avg_time_on_page = db.session.query(func.avg(CrawlerVisit.time_on_page)).filter(
            CrawlerVisit.timestamp >= cutoff,
            CrawlerVisit.time_on_page != None
        ).scalar()
        
        # Scroll depth metrics
        avg_scroll_depth = db.session.query(func.avg(CrawlerVisit.scroll_depth)).filter(
            CrawlerVisit.timestamp >= cutoff,
            CrawlerVisit.scroll_depth != None
        ).scalar()
        
        # Visitor trends over time
        visitor_trends = db.session.query(
            func.date(CrawlerVisit.timestamp).label('date'),
            func.count(CrawlerVisit.id).label('visits')
        ).filter(
            CrawlerVisit.timestamp >= cutoff
        ).group_by(
            'date'
        ).order_by(
            'date'
        ).all()
        
        dates = [str(record.date) for record in visitor_trends]
        visit_counts = [record.visits for record in visitor_trends]
        
        # Average bot confidence per path
        avg_bot_confidence = db.session.query(
            CrawlerVisit.path,
            func.avg(CrawlerVisit.bot_confidence).label('avg_confidence')
        ).filter(
            CrawlerVisit.timestamp >= cutoff
        ).group_by(
            CrawlerVisit.path
        ).order_by(
            desc('avg_confidence')
        ).limit(10).all()
        
        # Most visited pages
        top_pages = db.session.query(
            CrawlerVisit.path,
            func.count(CrawlerVisit.id).label('count')
        ).filter(
            CrawlerVisit.timestamp >= cutoff
        ).group_by(
            CrawlerVisit.path
        ).order_by(
            desc('count')
        ).limit(10).all()
        
        stats = {
            'total_visits': total_visits,
            'crawler_visits': crawler_visits,
            'human_visits': human_visits,
            'top_crawlers': top_crawlers,
            'devices': devices,
            'avg_time_on_page': round(avg_time_on_page or 0, 2),
            'avg_scroll_depth': round(avg_scroll_depth or 0, 2),
            'dates': dates,
            'visit_counts': visit_counts,
            'crawler_visits_count': crawler_visits,
            'human_visits_count': human_visits,
            'avg_bot_confidence': avg_bot_confidence,
            'top_pages': top_pages
        }
        
        return render_template('analytics.html', stats=stats, days=days)
    except Exception as e:
        logger.error(f"Error in analytics route: {str(e)}")
        return str(e), 500

# API Endpoints
@app.route('/api/posts')
def get_posts():
    try:
        page = request.args.get('page', 1, type=int)
        posts_query = BlogPost.query.order_by(BlogPost.created_at.desc())
        total_posts = posts_query.count()
        posts = posts_query.offset((page - 1) * POSTS_PER_PAGE).limit(POSTS_PER_PAGE).all()
        
        posts_data = [
            {
                'title': post.title,
                'slug': post.slug,
                'created_at': post.created_at.strftime('%Y-%m-%d'),
                'image': post.image,
                'content': post.content[:200] + '...'
            } for post in posts
        ]
        
        return jsonify({
            'posts': posts_data,
            'has_more': (page * POSTS_PER_PAGE) < total_posts
        })
    except Exception as e:
        logger.error(f"Error fetching posts: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500

@app.route('/api/log_time', methods=['POST'])
def log_time():
    data = request.get_json()
    path = data.get('path')
    time_on_page = data.get('time_on_page')
    log_visit(request, path, time_on_page=time_on_page)
    return '', 204

@app.route('/api/log_scroll', methods=['POST'])
def log_scroll():
    data = request.get_json()
    path = data.get('path')
    scroll_depth = data.get('scroll_depth')
    log_visit(request, path, scroll_depth=scroll_depth)
    return '', 204

@app.route('/api/set_theme', methods=['POST'])
def set_theme():
    data = request.get_json()
    theme = data.get('theme', 'light')
    session['theme'] = theme
    return jsonify({'status': 'success'}), 200

# Real-Time Visitor Tracking
active_users = 0

@socketio.on('connect')
def handle_connect():
    global active_users
    active_users += 1
    emit('update_users', {'active_users': active_users}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    global active_users
    active_users -= 1
    emit('update_users', {'active_users': active_users}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
