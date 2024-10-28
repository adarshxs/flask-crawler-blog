# app.py
import os
import logging
import urllib.parse
from flask import Flask, render_template, request, Response, abort, jsonify
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, func, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import random
import base64
import io
from PIL import Image
import user_agents
import json
import hashlib
import ipaddress
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database setup (your existing setup code here...)

class BlogPost(Base):
    __tablename__ = 'blog_posts'
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    content = Column(Text)
    image = Column(Text)
    slug = Column(String(200), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    view_count = Column(Integer, default=0)
    generated = Column(Boolean, default=False)

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
    time_spent = Column(Integer, default=0)  # in seconds
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

def generate_title():
    topics = ['Web Crawling', 'SEO', 'Digital Marketing', 'Content Strategy', 
              'Search Engines', 'Analytics', 'Bot Detection', 'Web Scraping',
              'Data Mining', 'Machine Learning']
    actions = ['Understanding', 'Mastering', 'Deep Dive into', 'Guide to',
               'Evolution of', 'Future of', 'Best Practices for', 'Analysis of']
    
    return f"{random.choice(actions)} {random.choice(topics)}"

def generate_content():
    paragraphs = [
        "In the ever-evolving landscape of digital technology, understanding web crawlers and their behavior becomes increasingly crucial.",
        "Search engines employ sophisticated algorithms to traverse the web, discovering and indexing content that shapes our online experience.",
        "Modern web architecture must account for both human users and automated crawlers, ensuring optimal accessibility and performance.",
        "Data analysis reveals patterns in crawler behavior, enabling better optimization strategies and improved search engine visibility.",
        "Security considerations play a vital role in managing crawler access while protecting sensitive information."
    ]
    
    # Generate more paragraphs using combinations and variations
    additional = []
    for _ in range(5):
        base = random.choice(paragraphs)
        modified = base.replace(
            random.choice(base.split()),
            random.choice(['effectively', 'systematically', 'fundamentally', 'strategically'])
        )
        additional.append(modified)
    
    return "\n\n".join(paragraphs + additional)

def log_visit(request, path):
    try:
        with Session() as session:
            user_agent_string = request.headers.get('User-Agent', '')
            ip_address = request.remote_addr
            referrer = request.referrer
            user_agent = user_agents.parse(user_agent_string)
            session_id = request.cookies.get('session_id', str(uuid.uuid4()))
            
            # Enhance crawler detection
            is_crawler = user_agent.is_bot or any(bot in user_agent_string.lower() 
                for bot in ['bot', 'crawler', 'spider', 'slurp', 'baiduspider'])
            
            visit = CrawlerVisit(
                user_agent=user_agent_string,
                ip_address=ip_address,
                path=path,
                is_crawler=is_crawler,
                crawler_name=user_agent.browser.family if is_crawler else None,
                session_id=session_id,
                referrer=referrer,
                device_type=user_agent.device.family,
                browser_family=user_agent.browser.family,
                os_family=user_agent.os.family,
                last_activity=datetime.utcnow()
            )
            session.add(visit)
            
            # Log page view
            page_view = PageView(
                session_id=session_id,
                page_url=path,
                timestamp=datetime.utcnow()
            )
            session.add(page_view)
            
            session.commit()
            return session_id
            
    except Exception as e:
        logger.error(f"Error logging visit: {str(e)}")
        return None

@app.route('/')
def home():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        with Session() as session:
            session_id = log_visit(request, '/')
            
            # Get total posts count
            total_posts = session.query(BlogPost).count()
            
            # If we need more posts, generate them
            if total_posts < (page * per_page) + 10:
                for _ in range(20):  # Generate 20 more posts
                    title = generate_title()
                    content = generate_content()
                    slug = '-'.join(title.lower().split())
                    image = generate_random_image()
                    
                    post = BlogPost(
                        title=title,
                        content=content,
                        image=image,
                        slug=slug,
                        generated=True
                    )
                    session.add(post)
                session.commit()
            
            # Get paginated posts
            posts = session.query(BlogPost)\
                         .order_by(BlogPost.created_at.desc())\
                         .offset((page - 1) * per_page)\
                         .limit(per_page)\
                         .all()
            
            return render_template('home.html', 
                                posts=posts, 
                                page=page,
                                has_next=True)  # Always true due to infinite generation
            
    except Exception as e:
        logger.error(f"Error in home route: {str(e)}")
        return str(e), 500

@app.route('/post/<slug>')
def post(slug):
    try:
        with Session() as session:
            post = session.query(BlogPost).filter_by(slug=slug).first()
            if not post:
                abort(404)
                
            session_id = log_visit(request, f'/post/{slug}')
            
            # Update view count
            post.view_count += 1
            
            # Get related posts
            related_posts = session.query(BlogPost)\
                                 .filter(BlogPost.slug != slug)\
                                 .order_by(func.random())\
                                 .limit(5)\
                                 .all()
            
            session.commit()
            
            return render_template('post.html', 
                                 post=post, 
                                 related_posts=related_posts)
    except Exception as e:
        logger.error(f"Error in post route: {str(e)}")
        return str(e), 500

@app.route('/admin/analytics')
def analytics():
    try:
        with Session() as session:
            # Get time range from query params
            days = request.args.get('days', 7, type=int)
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Basic stats
            total_visits = session.query(CrawlerVisit)\
                                .filter(CrawlerVisit.timestamp > start_date)\
                                .count()
            
            crawler_visits = session.query(CrawlerVisit)\
                                  .filter(CrawlerVisit.timestamp > start_date)\
                                  .filter(CrawlerVisit.is_crawler == True)\
                                  .count()
            
            # Top crawlers
            top_crawlers = session.query(
                CrawlerVisit.crawler_name,
                func.count(CrawlerVisit.id).label('visit_count')
            ).filter(
                CrawlerVisit.is_crawler == True,
                CrawlerVisit.timestamp > start_date
            ).group_by(
                CrawlerVisit.crawler_name
            ).order_by(
                desc('visit_count')
            ).limit(10).all()
            
            # Most viewed pages
            top_pages = session.query(
                PageView.page_url,
                func.count(PageView.id).label('view_count')
            ).filter(
                PageView.timestamp > start_date
            ).group_by(
                PageView.page_url
            ).order_by(
                desc('view_count')
            ).limit(10).all()
            
            # Device statistics
            devices = session.query(
                CrawlerVisit.device_type,
                func.count(CrawlerVisit.id).label('count')
            ).filter(
                CrawlerVisit.timestamp > start_date
            ).group_by(
                CrawlerVisit.device_type
            ).all()
            
            stats = {
                'total_visits': total_visits,
                'crawler_visits': crawler_visits,
                'human_visits': total_visits - crawler_visits,
                'top_crawlers': top_crawlers,
                'top_pages': top_pages,
                'devices': devices
            }
            
            return render_template('analytics.html', stats=stats, days=days)
            
    except Exception as e:
        logger.error(f"Error in analytics route: {str(e)}")
        return str(e), 500

@app.route('/api/track', methods=['POST'])
def track_activity():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        activity_type = data.get('type')
        
        with Session() as session:
            page_view = session.query(PageView)\
                             .filter_by(session_id=session_id)\
                             .order_by(PageView.timestamp.desc())\
                             .first()
            
            if page_view:
                if activity_type == 'scroll':
                    page_view.scroll_depth = data.get('scroll_depth', 0)
                elif activity_type == 'time':
                    page_view.time_spent = data.get('time_spent', 0)
                    page_view.is_bounce = False
                
                session.commit()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error tracking activity: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True)