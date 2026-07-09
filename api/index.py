"""
Vercel WSGI entry point for TrackWise Flask application.

This module provides the serverless-compatible entry point for Vercel deployment.
It handles the Flask application server-side and provides fallback behavior
for background tasks that aren't available in serverless environments.
"""

import os
import sys

# Add project root to path for imports
# api/index.py -> project root (one level up from api/)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Force production environment on Vercel (prevents SQLite fallback to read-only instance path)
os.environ['FLASK_ENV'] = 'production'

# Disable Celery in serverless mode (tasks run synchronously)
os.environ.setdefault('CELERY_DISABLED', 'true')

# Configure WeasyPrint cache directory for serverless (ephemeral /tmp)
os.environ.setdefault('WEASYPRINT_CACHEDIR', '/tmp/weasyprint-cache')

# Configure instance path for serverless (ephemeral /tmp for SQLite fallback)
os.environ.setdefault('INSTANCE_PATH', '/tmp/instance')

# Change working directory to project root for relative paths
os.chdir(PROJECT_ROOT)

# Import and create the Flask app
from app import create_app

# Create app instance at module level for serverless warm starts
app = create_app()

# Vercel Python builder expects the Flask app to be exposed as `app`
# The builder will handle WSGI conversion automatically