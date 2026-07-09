"""Business-scoped query mixin for multi-tenant data isolation."""

from flask import g
from sqlalchemy.orm import declared_attr
from models import db


class BusinessScopedMixin:
    """Mixin that adds business_id FK and auto-scopes queries.

    Usage:
        class MyModel(BusinessScopedMixin, db.Model):
            __tablename__ = 'my_models'
            ...
    """

    @declared_attr
    def business_id(cls):
        return db.Column(
            db.Integer,
            db.ForeignKey('businesses.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        )

    @classmethod
    def _business_filter(cls):
        """Return the filter expression for the current business."""
        from flask import has_request_context, current_app

        if not has_request_context():
            return cls.business_id.isnot(None)  # fallback for CLI

        # In testing mode with LOGIN_DISABLED, skip filtering
        if current_app.testing and current_app.config.get('LOGIN_DISABLED'):
            return cls.business_id.isnot(None)

        biz_id = getattr(g, 'business_id', None)
        if biz_id is not None:
            return cls.business_id == biz_id
        return cls.business_id.isnot(None)

    @classmethod
    def query(cls):
        """Return a query auto-filtered by business_id."""
        return db.session.query(cls).filter(cls._business_filter())