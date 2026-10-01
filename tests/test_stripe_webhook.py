"""Stripe webhook: signature enforcement and idempotent processing."""

import json

from app.api.webhooks import _construct_event


def _post_event(client, app, event, monkeypatch=None, signature="sig"):
    if monkeypatch is not None:
        monkeypatch.setattr(
            "app.api.webhooks._construct_event",
            lambda payload, sig, secret: event if sig == signature else None,
        )
    return client.post(
        "/api/stripe/webhook",
        data=json.dumps(event),
        headers={"Stripe-Signature": signature, "Content-Type": "application/json"},
    )


def _sub_event(event_id, sub_id="sub_123", status="active"):
    return {
        "id": event_id,
        "type": "customer.subscription.updated",
        "data": {"object": {"id": sub_id, "status": status}},
    }


def test_webhook_rejects_missing_signature(app, client):
    app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
    response = client.post(
        "/api/stripe/webhook",
        data=json.dumps({"id": "evt_x", "type": "customer.subscription.updated"}),
    )
    assert response.status_code == 400


def test_webhook_rejects_unconfigured_secret(app, client, monkeypatch):
    app.config["STRIPE_WEBHOOK_SECRET"] = None
    response = client.post(
        "/api/stripe/webhook",
        data="{}",
        headers={"Stripe-Signature": "sig"},
    )
    assert response.status_code == 400


def test_webhook_rejects_bad_signature(app, client, monkeypatch):
    app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
    monkeypatch.setattr(
        "app.api.webhooks._construct_event",
        lambda payload, sig, secret: None,
    )
    response = client.post(
        "/api/stripe/webhook",
        data="{}",
        headers={"Stripe-Signature": "forged"},
    )
    assert response.status_code == 400


def test_webhook_idempotent_and_updates_subscription(app, client, monkeypatch, business):
    from models import db, Subscription, Plan, ProcessedStripeEvent

    app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

    plan = Plan(name="Starter", price=29, max_users=3, features="{}", is_active=True)
    db.session.add(plan)
    db.session.flush()
    subscription = Subscription(
        business_id=business.id,
        plan_id=plan.id,
        status="past_due",
        stripe_subscription_id="sub_123",
    )
    db.session.add(subscription)
    db.session.commit()

    event = _sub_event("evt_first", status="active")
    response = _post_event(client, app, event, monkeypatch)
    assert response.status_code == 200
    assert response.json["received"] is True
    assert subscription.status == "active"
    assert ProcessedStripeEvent.query.filter_by(event_id="evt_first").count() == 1

    # Replay: same event id → recorded success, no second application.
    response = _post_event(client, app, event, monkeypatch)
    assert response.status_code == 200
    assert response.json["duplicate"] is True
    assert ProcessedStripeEvent.query.filter_by(event_id="evt_first").count() == 1
    assert Subscription.query.filter_by(stripe_subscription_id="sub_123").count() == 1


def test_construct_event_rejects_garbage_without_secret():
    class FakeError(Exception):
        pass

    import sys, types

    fake_stripe = types.ModuleType("stripe")
    fake_stripe.error = types.SimpleNamespace(SignatureVerificationError=FakeError)

    class _Webhook:
        @staticmethod
        def construct_event(payload, sig, secret):
            if not secret:
                raise FakeError()
            return json.loads(payload)

    fake_stripe.Webhook = _Webhook
    monkey_module = {"stripe": fake_stripe}
    import app.api.webhooks as webhooks
    import unittest.mock as mock

    with mock.patch.dict(sys.modules, monkey_module):
        assert _construct_event(b"payload", "sig", None) is None
