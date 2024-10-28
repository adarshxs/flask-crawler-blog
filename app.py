# app.py
import os
import logging
import urllib.parse
from flask import Flask, render_template, request, Response
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import random
import base64
import io
from PIL import Image
import user_agents

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database connection
server = os.environ.get('AZURE_SQL_SERVER', '')
database = os.environ.get('AZURE_SQL_DATABASE', '')
username = os.environ.get('AZURE_SQL_USER', '')
password = os.environ.get('AZURE_SQL_PASSWORD', '')
driver = '{ODBC Driver 17 for SQL Server}'

if not all([server, database, username, password]):
    raise ValueError("Missing database connection parameters. Please check your environment variables.")

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
Base = declarative_base()

# Models
class BlogPost(Base):
    __tablename__ = 'blog_posts'
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    content = Column(Text)
    image = Column(Text)
    slug = Column(String(200), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CrawlerVisit(Base):
    __tablename__ = 'crawler_visits'
    id = Column(Integer, primary_key=True)
    user_agent = Column(String(500))
    ip_address = Column(String(50))
    timestamp = Column(DateTime, default=datetime.utcnow)
    path = Column(String(200))
    is_crawler = Column(Boolean, default=False)
    crawler_name = Column(String(200))

def generate_random_image():
    """Generate a random colored image with base64 encoding"""
    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img = Image.new('RGB', (400, 300), color)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def generate_sample_content():
    """Generate sample blog post content"""
    paragraphs = [
        "This is a sample blog post paragraph that discusses web crawling and SEO best practices.",
        "Search engines use sophisticated algorithms to index and rank web content effectively.",
        "Understanding how web crawlers work is essential for optimizing your website's visibility."
    ]
    return "\n\n".join(paragraphs)

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
                crawler_name=crawler_name
            )
            session.add(visit)
            session.commit()
            logger.info(f"Logged visit: {path} from {ip_address}")
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
            post = session.query(BlogPost).filter_by(slug=slug).first_or_404()
            log_visit(request, f'/post/{slug}')
            random_posts = session.query(BlogPost).filter(BlogPost.slug != slug).order_by(func.random()).limit(3).all()
            return render_template('post.html', post=post, random_posts=random_posts)
    except Exception as e:
        logger.error(f"Error in post route: {str(e)}")
        return str(e), 500

@app.route('/admin')
def admin():
    try:
        with Session() as session:
            visits = session.query(CrawlerVisit).order_by(CrawlerVisit.timestamp.desc()).limit(100).all()
            return render_template('admin.html', visits=visits)
    except Exception as e:
        logger.error(f"Error in admin route: {str(e)}")
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
                    "content": "Learn about web crawlers and their importance in modern search engines.",
                    "slug": "intro-web-crawling"
                },
                {
                    "title": "SEO Best Practices 2024",
                    "content": "Discover the latest SEO techniques and optimization strategies.",
                    "slug": "seo-best-practices"
                },
                {
                    "title": "Understanding Search Engine Bots",
                    "content": "Deep dive into how search engine bots work and index content.",
                    "slug": "search-engine-bots"
                },
                {
                    "title": "Optimizing Your Website for Crawlers",
                    "content": "Learn how to make your website more crawler-friendly.",
                    "slug": "crawler-optimization"
                },
                {
                    "title": "The Future of Web Indexing",
                    "content": "Explore upcoming trends in web indexing and search technology.",
                    "slug": "future-web-indexing"
                }
            ]
            
            # Create posts
            for post_data in posts_data:
                post = BlogPost(
                    title=post_data["title"],
                    content=post_data["content"] + "\n\n" + generate_sample_content(),
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