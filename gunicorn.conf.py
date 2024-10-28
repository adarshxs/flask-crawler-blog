# gunicorn.conf.py

bind = "0.0.0.0:8000"
workers = 1  # eventlet works best with a single worker
worker_class = 'eventlet'
timeout = 120
