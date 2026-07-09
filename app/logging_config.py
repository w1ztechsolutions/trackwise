"""Structured logging configuration for production."""

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for production log aggregation."""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id

        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id

        if hasattr(record, 'business_id'):
            log_entry['business_id'] = record.business_id

        if record.exc_info and record.exc_info[0]:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(app):
    """Configure structured logging for the Flask application.

    In production, logs are JSON-formatted for log aggregation tools.
    In development, standard console logging is used.
    """
    log_level = logging.DEBUG if app.debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if app.config.get('ENV') == 'production':
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )

    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    # Configure Flask logger
    app.logger.setLevel(log_level)
    app.logger.addHandler(handler)

    # Suppress noisy loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    return app