# app.py
import os
import logging
import urllib.parse
from flask import Flask, render_template, request, Response
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base  # Add this import
from datetime import datetime
import random
import base64
import io
from PIL import Image
import user_agents

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy
Base = declarative_base()

# Define models
class BlogPost(Base):
    __tablename__ = 'blog_posts'
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    content = Column(Text)
    image = Column(Text)
    slug = Column(String(200), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    view_count = Column(Integer, default=0)

class CrawlerVisit(Base):
    __tablename__ = 'crawler_visits'
    id = Column(Integer, primary_key=True)
    user_agent = Column(String(500))
    ip_address = Column(String(50))
    timestamp = Column(DateTime, default=datetime.utcnow)
    path = Column(String(200))
    is_crawler = Column(Boolean, default=False)
    crawler_name = Column(String(200))
    session_id = Column(String(100))
    referrer = Column(String(500))
    device_type = Column(String(50))
    browser_family = Column(String(50))
    os_family = Column(String(50))
    time_spent = Column(Integer, default=0)
    last_activity = Column(DateTime)

class PageView(Base):
    __tablename__ = 'page_views'
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100))
    page_url = Column(String(500))
    timestamp = Column(DateTime, default=datetime.utcnow)
    time_spent = Column(Integer, default=0)
    scroll_depth = Column(Integer, default=0)
    is_bounce = Column(Boolean, default=True)

# Initialize Flask
app = Flask(__name__)

# Database connection
server = os.environ.get('AZURE_SQL_SERVER', '')
database = os.environ.get('AZURE_SQL_DATABASE', '')
username = os.environ.get('AZURE_SQL_USER', '')
password = os.environ.get('AZURE_SQL_PASSWORD', '')
driver = '{ODBC Driver 17 for SQL Server}'

if not all([server, database, username, password]):
    logger.warning("Missing database parameters, using development settings")
    # For local development, you might want to set default values
    server = 'localhost'
    database = 'test'
    username = 'sa'
    password = 'password'

params = urllib.parse.quote_plus(
    f"DRIVER={driver};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    "TrustServerCertificate=yes;"
)

connection_string = f"mssql+pyodbc:///?odbc_connect={params}"
engine = create_engine(connection_string)
Session = sessionmaker(bind=engine)

def generate_random_image():
    """Generate a random colored image with base64 encoding"""
    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img = Image.new('RGB', (400, 300), color)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def log_visit(request, path):
    """Log visitor information"""
    try:
        with Session() as session:
            user_agent_string = request.headers.get('User-Agent', '')
            ip_address = request.remote_addr
            user_agent = user_agents.parse(user_agent_string)
            
            is_crawler = user_agent.is_bot
            crawler_name = user_agent.browser.family if is_crawler else None

            visit = CrawlerVisit(
                user_agent=user_agent_string,
                ip_address=ip_address,
                path=path,
                is_crawler=is_crawler,
                crawler_name=crawler_name,
                device_type=user_agent.device.family,
                browser_family=user_agent.browser.family,
                os_family=user_agent.os.family,
                last_activity=datetime.utcnow()
            )
            session.add(visit)
            session.commit()
    except Exception as e:
        logger.error(f"Error logging visit: {str(e)}")

@app.route('/')
def home():
    try:
        with Session() as session:
            log_visit(request, '/')
            posts = session.query(BlogPost).order_by(BlogPost.created_at.desc()).all()
            return render_template('home.html', posts=posts)
    except Exception as e:
        logger.error(f"Error in home route: {str(e)}")
        return str(e), 500

@app.route('/post/<slug>')
def post(slug):
    try:
        with Session() as session:
            post = session.query(BlogPost).filter_by(slug=slug).first()
            if not post:
                return "Post not found", 404
                
            log_visit(request, f'/post/{slug}')
            
            # Get random related posts
            related_posts = session.query(BlogPost)\
                .filter(BlogPost.slug != slug)\
                .order_by(func.random())\
                .limit(3)\
                .all()
            
            return render_template('post.html', post=post, related_posts=related_posts)
    except Exception as e:
        logger.error(f"Error in post route: {str(e)}")
        return str(e), 500

@app.cli.command('init-db')
def init_db_command():
    """Initialize the database."""
    try:
        Base.metadata.create_all(engine)
        print('Database initialized successfully.')
    except Exception as e:
        print(f'Error initializing database: {str(e)}')
        raise e

@app.cli.command('create-sample-posts')
def create_sample_posts_command():
    """Create sample blog posts."""
    try:
        with Session() as session:
            # Clear existing posts
            session.query(BlogPost).delete()
            
            # Sample blog post data
            posts_data = [
                {
                    "title": "Introduction to Web Crawling",
                    "content": "Learn about web crawlers and their importance...",
                    "slug": "intro-web-crawling"
                },
                {
                    "title": "SEO Best Practices",
                    "content": "Discover the latest SEO techniques...",
                    "slug": "seo-best-practices"
                }
            ]
            
            # Create posts
            for post_data in posts_data:
                post = BlogPost(
                    title=post_data["title"],
                    content=post_data["content"],
                    image=generate_random_image(),
                    slug=post_data["slug"]
                )
                session.add(post)
            
            session.commit()
            print('Sample posts created successfully.')
    except Exception as e:
        print(f'Error creating sample posts: {str(e)}')
        raise e

if __name__ == '__main__':
    app.run(debug=True)