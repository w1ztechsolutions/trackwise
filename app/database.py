"""Request-scoped routing between the production and isolated demo databases."""

import os

from flask import current_app, has_request_context, session as flask_session
from flask_login import current_user, logout_user
from flask_sqlalchemy.session import Session as FlaskSession
from sqlalchemy.engine import make_url
from sqlalchemy.exc import UnboundExecutionError

from app.models import db


DATABASE_CONTEXT_KEY = "_trackwise_database_context"
PRODUCTION_CONTEXT = "production"
DEMO_CONTEXT = "demo"


def database_identity(uri):
    """Return a password-free identity for detecting obviously shared endpoints."""
    parsed = make_url(uri)
    dialect = parsed.drivername.partition("+")[0]
    host = (parsed.host or "").lower()
    if host.endswith(".neon.tech"):
        host = host.replace("-pooler.", ".")

    database = parsed.database
    if dialect == "sqlite":
        if database in {None, "", ":memory:"}:
            database = ":memory:"
        else:
            database = os.path.abspath(database)
    return dialect, host, parsed.port, database


class DatabaseRoutingSession(FlaskSession):
    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        if bind is not None:
            return bind
        if (
            has_request_context()
            and flask_session.get(DATABASE_CONTEXT_KEY) == DEMO_CONTEXT
        ):
            engine = current_app.extensions.get("trackwise_demo_engine")
            if engine is None:
                raise UnboundExecutionError(
                    "This session belongs to the demo database, which is not configured."
                )
            return engine
        return super().get_bind(
            mapper=mapper,
            clause=clause,
            bind=bind,
            **kwargs,
        )


def install_database_routing():
    factory = db.session.session_factory
    factory.class_ = DatabaseRoutingSession
    factory.kw.pop("class_", None)


def select_database(context):
    """Log out the prior database identity before routing this request elsewhere."""
    if context not in {PRODUCTION_CONTEXT, DEMO_CONTEXT}:
        raise ValueError(f"Unknown database context: {context}")

    if context == DEMO_CONTEXT and current_app.extensions.get("trackwise_demo_engine") is None:
        raise UnboundExecutionError("The isolated demo database is not configured.")

    if current_user.is_authenticated:
        logout_user()

    db.session.remove()
    flask_session[DATABASE_CONTEXT_KEY] = context
