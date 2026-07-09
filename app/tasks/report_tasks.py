"""Background tasks for report generation and email sending."""

import json
import os
from datetime import datetime, timezone

from app.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def generate_report_pdf(self, business_id, report_type, params=None):
    """Generate a PDF report in the background.

    Args:
        business_id: The business ID
        report_type: Type of report (income_statement, balance_sheet, etc.)
        params: Dict with start_date, end_date, etc.

    Returns:
        Dict with status and file path
    """
    try:
        from app import create_app
        from app.services.reports import (
            get_income_statement,
            get_balance_sheet,
            get_cash_flow,
            get_trial_balance,
        )

        app = create_app()
        with app.app_context():
            if params is None:
                params = {}

            report_data = None
            if report_type == 'income_statement':
                report_data = get_income_statement(
                    business_id,
                    start_date=params.get('start_date'),
                    end_date=params.get('end_date'),
                )
            elif report_type == 'balance_sheet':
                report_data = get_balance_sheet(business_id)
            elif report_type == 'cash_flow':
                report_data = get_cash_flow(business_id)
            elif report_type == 'trial_balance':
                report_data = get_trial_balance(business_id)

            # Generate PDF using WeasyPrint
            from weasyprint import HTML
            from flask import render_template

            html = render_template(
                f'reports/{report_type}_pdf.html',
                report=report_data,
                generated_at=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),
            )

            output_dir = os.path.join(app.instance_path, 'reports')
            os.makedirs(output_dir, exist_ok=True)
            filename = f'{report_type}_{business_id}_{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}.pdf'
            filepath = os.path.join(output_dir, filename)

            HTML(string=html).write_pdf(filepath)

            return {
                'status': 'success',
                'filepath': filepath,
                'filename': filename,
            }
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@celery_app.task
def send_email(recipient, subject, body):
    """Send an email notification.

    Placeholder - requires SMTP configuration.
    """
    # TODO: Implement actual email sending with SMTP
    # import smtplib
    # from email.mime.text import MIMEText
    # ...
    return {
        'status': 'not_implemented',
        'recipient': recipient,
        'subject': subject,
    }


@celery_app.task
def precompute_dashboard(business_id):
    """Precompute and cache dashboard KPIs for faster loading."""
    try:
        from app import create_app
        from services.fifo_service import get_profit_loss, get_inventory_valuation

        app = create_app()
        with app.app_context():
            # Compute and cache key metrics
            pl = get_profit_loss()
            valuation = get_inventory_valuation()

            # Store in Redis for quick retrieval
            cache_key = f'dashboard:{business_id}'
            cache_data = {
                'total_sales': pl['total_sales'],
                'total_cogs': pl['total_cogs'],
                'gross_profit': pl['gross_profit'],
                'net_profit': pl['net_profit'],
                'inventory_valuation': valuation['total_valuation'],
                'computed_at': datetime.now(timezone.utc).isoformat(),
            }

            # TODO: Store in Redis when Redis is available
            # from redis import Redis
            # r = Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))
            # r.setex(cache_key, 300, json.dumps(cache_data))

            return cache_data
    except Exception as e:
        return {'error': str(e)}