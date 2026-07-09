"""Celery configuration for background task processing.

In serverless environments (Vercel), Celery is disabled by default.
Set CELERY_DISABLED=false to enable if you have external Redis.
"""

import os


# Check if Celery is disabled (default for serverless)
CELERY_DISABLED = os.environ.get('CELERY_DISABLED', 'true').lower() == 'true'

# Default Redis URL for external services
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')


# Create a mock Celery app for serverless mode
class MockCelery:
    """Mock Celery that executes tasks synchronously in serverless mode."""
    
    def task(self, *args, **kwargs):
        def decorator(f):
            def wrapper(*args2, **kwargs2):
                return f(*args2, **kwargs2)
            wrapper.delay = wrapper
            wrapper.apply_async = wrapper
            wrapper.si = lambda: wrapper
            return wrapper
        return decorator
    
    def __call__(self, *args, **kwargs):
        pass


if CELERY_DISABLED:
    celery_app = MockCelery()
else:
    from celery import Celery
    
    celery_app = Celery(
        'trackwise',
        broker=REDIS_URL,
        backend=REDIS_URL,
        include=['app.tasks.report_tasks'],
    )
    celery_app.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Africa/Johannesburg',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,
        task_soft_time_limit=15 * 60,
        worker_max_tasks_per_child=200,
    )