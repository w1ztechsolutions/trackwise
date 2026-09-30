"""Shared creation of configured transaction approval requests."""

import json

from app.models import db
from app.models.approval import ApprovalConfig, ApprovalRequest


def create_approval_request(business_id, transaction_type, transaction_id, created_by):
    config = ApprovalConfig.query.filter_by(
        business_id=business_id,
        transaction_type=transaction_type,
        is_active=True,
    ).first()
    if config is None:
        return None

    levels = json.loads(config.levels) if config.levels else []
    if not levels:
        return None

    request = ApprovalRequest(
        business_id=business_id,
        transaction_type=transaction_type,
        transaction_id=transaction_id,
        current_level=0,
        status="pending",
        created_by=created_by,
    )
    db.session.add(request)
    return request
