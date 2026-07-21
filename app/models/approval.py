"""Approval workflow models for multi-level transaction approval."""

from datetime import datetime, timezone
from models import db


class ApprovalConfig(db.Model):
    """Defines approval workflow configuration for each transaction type per business.

    The admin sets which transaction types require approval and at which levels.
    levels is a JSON array of role names in order, e.g. ["accountant", "manager"]
    """
    __tablename__ = 'approval_configs'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    transaction_type = db.Column(db.String(50), nullable=False)
    # JSON array of role names in approval order, e.g. ["accountant", "manager"]
    levels = db.Column(db.Text, nullable=False, default='[]')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('business_id', 'transaction_type', name='uq_business_approval_type'),
    )

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'business_id': self.business_id,
            'transaction_type': self.transaction_type,
            'levels': json.loads(self.levels) if self.levels else [],
            'is_active': self.is_active,
        }


class ApprovalRequest(db.Model):
    """Tracks a pending approval request for a specific transaction.

    current_level starts at 0 and increments as each level approves.
    """
    __tablename__ = 'approval_requests'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    transaction_type = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.Integer, nullable=False)
    current_level = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | approved | rejected | completed
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)

    actions = db.relationship('ApprovalAction', backref='approval_request', cascade='all, delete-orphan',
                              order_by='ApprovalAction.level.asc()')

    def to_dict(self):
        return {
            'id': self.id,
            'business_id': self.business_id,
            'transaction_type': self.transaction_type,
            'transaction_id': self.transaction_id,
            'current_level': self.current_level,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ApprovalAction(db.Model):
    """Records each action taken on an approval request (approve/reject per level)."""
    __tablename__ = 'approval_actions'

    id = db.Column(db.Integer, primary_key=True)
    approval_request_id = db.Column(db.Integer, db.ForeignKey('approval_requests.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(20), nullable=False)  # approved | rejected
    level = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    actor = db.relationship('User', backref='approval_actions')

    def to_dict(self):
        return {
            'id': self.id,
            'approval_request_id': self.approval_request_id,
            'actor_id': self.actor_id,
            'action': self.action,
            'level': self.level,
            'comment': self.comment,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }