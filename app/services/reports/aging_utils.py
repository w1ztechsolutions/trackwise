"""Shared helpers for date-based receivable and payable aging."""

from datetime import datetime, time

from app.models import db


def normalize_as_of_date(value):
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.max)


def get_allocated_amounts(
    model,
    parent_id_column,
    date_column,
    business_id,
    as_of_date,
    require_approved=False,
):
    cutoff = normalize_as_of_date(as_of_date)
    query = db.session.query(
        parent_id_column,
        db.func.sum(model.amount),
    ).filter(
        model.business_id == business_id,
        parent_id_column.isnot(None),
        date_column <= cutoff,
    )
    if require_approved:
        query = query.filter(model.status == "approved")
    return {
        parent_id: float(amount or 0)
        for parent_id, amount in query.group_by(parent_id_column).all()
    }


def add_to_aging_buckets(buckets, reference_date, as_of_date, amount):
    if amount <= 0:
        return
    if reference_date is None:
        buckets["current"] += amount
        return

    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()
    as_of_day = normalize_as_of_date(as_of_date).date()
    days_overdue = (as_of_day - reference_date).days

    if days_overdue <= 30:
        buckets["current"] += amount
    elif days_overdue <= 60:
        buckets["days_30"] += amount
    elif days_overdue <= 90:
        buckets["days_60"] += amount
    else:
        buckets["days_90"] += amount
