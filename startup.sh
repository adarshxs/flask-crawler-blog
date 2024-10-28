#!/bin/bash

# Install ODBC Driver
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Initialize the database
python -m flask init-db
python -m flask create-sample-posts

# Start Gunicorn
gunicorn --config gunicorn.conf.py app:app