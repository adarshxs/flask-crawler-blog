# startup.sh

#!/bin/bash

# Install ODBC Driver
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Initialize the database and create tables
python -c "from app import Base, engine; Base.metadata.create_all(engine)"

# Create sample posts if none exist
python -c "from app import create_sample_posts; create_sample_posts()"

# Start Gunicorn with eventlet
gunicorn --worker-class eventlet --config gunicorn.conf.py app:app
