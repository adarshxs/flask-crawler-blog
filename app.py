# app.py
import os
import logging
import urllib.parse
from flask import Flask, render_template, request, Response, jsonify
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, func, desc
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

# Initialize SQLAlchemy
Base = declarative_base()

# Models
class BlogPost(Base):
    __tablename__ = 'blog_posts'
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    content = Column(Text)
    image = Column(Text)
    slug = Column(String(200))
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

# Initialize Flask
app = Flask(__name__)

# Database connection
server = os.environ.get('AZURE_SQL_SERVER', '')
database = os.environ.get('AZURE_SQL_DATABASE', '')
username = os.environ.get('AZURE_SQL_USER', '')
password = os.environ.get('AZURE_SQL_PASSWORD', '')
driver = '{ODBC Driver 17 for SQL Server}'

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

def create_sample_posts():
    """Create sample blog posts if none exist"""
    try:
        with Session() as session:
            # Check if we have any posts
            post_count = session.query(BlogPost).count()
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
                    session.add(post)
                session.commit()
                logger.info("Sample posts created successfully")
    except Exception as e:
        logger.error(f"Error creating sample posts: {str(e)}")

def log_visit(request, path):
    """Log visitor information"""
    try:
        with Session() as session:
            user_agent_string = request.headers.get('User-Agent', '')
            ip_address = request.remote_addr
            user_agent = user_agents.parse(user_agent_string)
            
            is_crawler = user_agent.is_bot or any(bot in user_agent_string.lower() 
                for bot in ['bot', 'crawler', 'spider'])
            
            visit = CrawlerVisit(
                user_agent=user_agent_string,
                ip_address=ip_address,
                path=path,
                is_crawler=is_crawler,
                crawler_name=user_agent.browser.family if is_crawler else None
            )
            session.add(visit)
            session.commit()
    except Exception as e:
        logger.error(f"Error logging visit: {str(e)}")

@app.route('/')
def home():
    try:
        create_sample_posts()
        
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
            
            # Get related posts
            related_posts = session.query(BlogPost)\
                .filter(BlogPost.slug != slug)\
                .order_by(func.random())\
                .limit(3)\
                .all()
            
            return render_template('post.html', post=post, related_posts=related_posts)
    except Exception as e:
        logger.error(f"Error in post route: {str(e)}")
        return str(e), 500

@app.route('/admin')
def admin():
    try:
        with Session() as session:
            # Get crawler statistics
            total_visits = session.query(CrawlerVisit).count()
            crawler_visits = session.query(CrawlerVisit).filter_by(is_crawler=True).count()
            
            # Get top crawlers
            top_crawlers = session.query(
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
                'human_visits': total_visits - crawler_visits,
                'top_crawlers': top_crawlers
            }
            
            return render_template('admin.html', stats=stats)
    except Exception as e:
        logger.error(f"Error in admin route: {str(e)}")
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True)