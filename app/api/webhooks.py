"""Stripe webhook endpoint: signature-verified, idempotent event processing.

The endpoint only accepts deliveries whose ``Stripe-Signature`` header verifies
against ``STRIPE_WEBHOOK_SECRET`` (via the Stripe SDK's ``construct_event``) —
unsigned or forged payloads are rejected with 400 before any processing. Every
accepted event id is inserted into the ``processed_stripe_events`` ledger; a
replayed delivery fails that unique insert and is answered with a no-op
success, so Stripe retries never apply an event twice.

Handler scope is deliberately limited to the subscription lifecycle this app
uses; unknown event types are recorded in the ledger and acknowledged.
"""

import logging

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

stripe_webhook_bp = Blueprint("stripe_webhook", __name__)


def _configured_secret():
    return current_app.config.get("STRIPE_WEBHOOK_SECRET") or None


def _construct_event(payload, signature, secret):
    import stripe

    try:
        return stripe.Webhook.construct_event(payload, signature, secret)
    except stripe.error.SignatureVerificationError:
        return None
    except (ValueError, KeyError):
        return None


def _subscription_for(stripe_subscription_id):
    from app.models import db, Subscription

    return db.session.query(Subscription).filter_by(
        stripe_subscription_id=stripe_subscription_id,
    ).first()


def _handle_checkout_completed(session_object):
    from app.models import Subscription

    subscription_id = (session_object.get("subscription") or "") if isinstance(session_object, dict) else getattr(session_object, "subscription", None)
    if not subscription_id:
        return
    subscription = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()
    if subscription is not None and subscription.status != "active":
        subscription.status = "active"


def _handle_subscription_update(event_object):
    from app.models import Subscription

    subscription_id = getattr(event_object, "id", None)
    if not subscription_id:
        return
    subscription = _subscription_for(subscription_id)
    if subscription is None:
        logger.info("Stripe webhook for unknown subscription %s (%s)", subscription_id, getattr(event_object, "status", "?"))
        return
    status = getattr(event_object, "status", None)
    if status:
        subscription.status = status


@stripe_webhook_bp.post("/api/stripe/webhook")
def stripe_webhook():
    from app.models import db, ProcessedStripeEvent
    from sqlalchemy.exc import IntegrityError

    payload = request.get_data()
    signature = request.headers.get("Stripe-Signature")
    secret = _configured_secret()

    if not secret:
        # Without the signing secret there is no way to trust a delivery.
        return jsonify({"error": "Stripe webhook not configured"}), 400
    if not signature:
        return jsonify({"error": "Missing Stripe-Signature header"}), 400

    event = _construct_event(payload, signature, secret)
    if event is None:
        return jsonify({"error": "Invalid webhook signature"}), 400

    # Idempotency: consume the event id first; replays fail the unique insert.
    ledger_entry = ProcessedStripeEvent(event_id=event["id"], type=event["type"])
    db.session.add(ledger_entry)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"received": True, "duplicate": True}), 200

    try:
        if event["type"] == "checkout.session.completed":
            _handle_checkout_completed(event["data"]["object"])
        elif event["type"] in {"customer.subscription.updated", "customer.subscription.deleted"}:
            _handle_subscription_update(event["data"]["object"])
        db.session.commit()
    except Exception:
        # A replayed delivery is required to reprocess a failed event.
        db.session.rollback()
        db.session.query(ProcessedStripeEvent).filter_by(event_id=event["id"]).delete()
        db.session.commit()
        logger.exception("Stripe event %s failed processing", event["id"])
        return jsonify({"error": "Webhook processing failed"}), 500

    return jsonify({"received": True}), 200


def register_stripe_webhook(app):
    from app import csrf

    app.register_blueprint(stripe_webhook_bp)
    # Stripe's servers cannot carry our CSRF token.
    csrf.exempt(stripe_webhook_bp)
