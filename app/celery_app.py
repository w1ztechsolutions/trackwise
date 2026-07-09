"""Celery configuration for background task processing."""

import os
from celery import Celery

# Default Redis URL
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

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
    timezone='Africa/Blantyre',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=15 * 60,
    worker_max_tasks_per_child=200,
)