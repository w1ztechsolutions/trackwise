"""Server-side upload size enforcement (413 before buffering)."""

import io


def test_upload_over_limit_rejected_413(app):
    app.config["MAX_CONTENT_LENGTH"] = 1024  # 1 KiB for the test
    client = app.test_client()

    response = client.post(
        "/sales/import/customers",
        data={"file": (io.BytesIO(b"x" * 2048), "too-big.xlsx")},
        content_length=2048,
    )
    assert response.status_code == 413


def test_max_content_length_configured(app):
    from flask import current_app

    with app.test_request_context():
        limit = current_app.config.get("MAX_CONTENT_LENGTH")
    assert limit is not None and limit > 0


def test_small_upload_not_rejected(app, client):
    """A small POST body passes the size guard (view outcome may differ)."""
    response = client.post(
        "/sales/import/customers",
        data={"file": (io.BytesIO(b"small"), "tiny.xlsx")},
    )
    assert response.status_code != 413
