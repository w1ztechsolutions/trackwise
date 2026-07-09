"""Gunicorn configuration for production."""

import os

# Socket binding
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')

# Worker configuration
workers = os.environ.get('GUNICORN_WORKERS', 4)
worker_class = 'sync'
timeout = 120
graceful_timeout = 30

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')

# Process naming
proc_name = 'trackwise'

# Server mechanics
preload_app = True
max_requests = 1000
max_requests_jitter = 100

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190