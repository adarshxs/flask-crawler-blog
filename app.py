from flask import Flask, render_template, request
import os
import json
from datetime import datetime
import random
import string

app = Flask(__name__)

# Use a JSON file for storage instead of a database
DATA_FILE = 'data.json'

def get_data():
    if not os.path.exists(DATA_FILE):
        return {"posts": [], "visitors": []}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def generate_sample_posts():
    if not os.path.exists(DATA_FILE):
        sample_posts = []
        for i in range(5):
            title = f"Sample Blog Post {i+1}"
            content = f"This is the content of blog post {i+1}. It contains sample text that a web crawler can analyze."
            post = {
                "id": i+1,
                "title": title,
                "content": content,
                "created_date": datetime.now().isoformat(),
                "image_url": f"https://picsum.photos/seed/{i+1}/800/400"
            }
            sample_posts.append(post)
        save_data({"posts": sample_posts, "visitors": []})

@app.before_request
def track_visitor():
    data = get_data()
    user_agent = request.headers.get('User-Agent', '')
    ip_address = request.remote_addr
    is_crawler = any(crawler in user_agent.lower() 
                    for crawler in ['bot', 'crawler', 'spider'])
    
    visitor = {
        "ip_address": ip_address,
        "user_agent": user_agent,
        "visit_date": datetime.now().isoformat(),
        "is_crawler": is_crawler
    }
    data["visitors"].append(visitor)
    save_data(data)

@app.route('/')
def home():
    generate_sample_posts()  # Ensure we have some posts
    data = get_data()
    return render_template('home.html', posts=data["posts"])

@app.route('/post/<int:post_id>')
def post(post_id):
    data = get_data()
    post = next((p for p in data["posts"] if p["id"] == post_id), None)
    if not post:
        return "Post not found", 404
    
    # Get random related posts
    related_posts = random.sample([p for p in data["posts"] if p["id"] != post_id], 
                                min(3, len(data["posts"])-1))
    return render_template('post.html', post=post, related_posts=related_posts)

@app.route('/admin')
def admin():
    data = get_data()
    crawler_stats = {}
    for visitor in data["visitors"]:
        if visitor["is_crawler"]:
            user_agent = visitor["user_agent"]
            if user_agent not in crawler_stats:
                crawler_stats[user_agent] = {
                    "visit_count": 0,
                    "last_visit": visitor["visit_date"]
                }
            crawler_stats[user_agent]["visit_count"] += 1
            
    return render_template('admin.html', crawler_stats=crawler_stats)

if __name__ == '__main__':
    app.run(debug=True)