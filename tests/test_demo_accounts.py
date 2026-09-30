import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Business, DemoWorkspace, Product, User, db
from app.database import database_identity
from app.services.demo_accounts import DEMO_ROLES


def _enable_demo_database(app):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db.metadata.create_all(bind=engine)
    app.extensions["trackwise_demo_engine"] = engine
    app.config["DEMO_MODE_ENABLED"] = True
    return engine


def test_demo_login_is_hidden_and_unavailable_by_default(app, client):
    app.config["DEMO_MODE_ENABLED"] = False

    response = client.get("/login")
    assert response.status_code == 200
    assert b"Explore the demo" not in response.data
    assert client.get("/demo").status_code == 404


def test_production_admin_can_still_open_user_creation(app, client):
    user_management = client.get("/users")
    assert user_management.status_code == 200
    assert b"Create User" in user_management.data
    assert client.get("/users/create").status_code == 200


def test_database_identity_rejects_neon_pooler_aliases():
    direct = "postgresql://demo_user:first@ep-example.us-east-2.aws.neon.tech/neondb"
    pooled = "postgresql+psycopg://demo_user:second@ep-example-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    assert database_identity(direct) == database_identity(pooled)


def test_app_factory_initializes_only_a_distinct_demo_database(tmp_path):
    from app import create_app

    class DualDatabaseConfig:
        TESTING = True
        SECRET_KEY = "test-secret"
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'production.db'}"
        SQLALCHEMY_ENGINE_OPTIONS = {}
        DEMO_MODE_ENABLED = True
        DEMO_DATABASE_URL = f"sqlite:///{tmp_path / 'demo.db'}"

    app = create_app(DualDatabaseConfig)
    try:
        with app.app_context():
            production_db = db.engine.url.database
            demo_db = app.extensions["trackwise_demo_engine"].url.database
            assert production_db != demo_db
    finally:
        with app.app_context():
            app.extensions["trackwise_demo_engine"].dispose()
            db.engine.dispose()

    same_database_config = type(
        "UnsafeDemoConfig",
        (DualDatabaseConfig,),
        {"DEMO_DATABASE_URL": DualDatabaseConfig.SQLALCHEMY_DATABASE_URI},
    )
    with pytest.raises(RuntimeError, match="different database endpoint"):
        create_app(same_database_config)


def test_new_demo_business_uses_demo_database_and_selected_role(app, client, business):
    demo_engine = _enable_demo_database(app)
    production_business_id = business.id
    response = client.get("/login")
    assert b"Explore the demo" in response.data
    demo_form = client.get("/demo")
    assert demo_form.status_code == 200
    assert b'id="bottomNav"' not in demo_form.data
    assert b'id="sidebarToggle"' not in demo_form.data
    for _, label in DEMO_ROLES:
        assert label.encode() in demo_form.data

    response = client.post(
        "/demo",
        data={"business_name": "  Acme   Demo ", "role": "cashier"},
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["_trackwise_database_context"] == "demo"
        demo_user_id = int(session["_user_id"])

    with Session(demo_engine) as demo_session:
        workspace = demo_session.query(DemoWorkspace).one()
        demo_business = demo_session.get(Business, workspace.business_id)
        demo_user = demo_session.get(User, demo_user_id)
        assert demo_business.name == "Acme Demo"
        assert demo_user.business_id == demo_business.id
        assert demo_user.role == "cashier"

    with app.app_context():
        db.session.add(Product(
            business_id=business.id,
            sku="PRODUCTION-ONLY",
            name="Production only",
            default_selling_price=1,
        ))
        db.session.commit()
    with Session(demo_engine) as demo_session:
        demo_session.add(Product(
            business_id=demo_business.id,
            sku="DEMO-ONLY",
            name="Demo only",
            default_selling_price=1,
        ))
        demo_session.commit()
    demo_products = client.get("/api/products")
    assert demo_products.status_code == 200
    product_skus = {product["sku"] for product in demo_products.get_json()}
    assert "DEMO-ONLY" in product_skus
    assert "PRODUCTION-ONLY" not in product_skus

    with app.app_context():
        assert db.session.query(Business).filter_by(name="Acme Demo").first() is None
        assert db.session.get(Business, production_business_id) is not None

    assert demo_engine is app.extensions["trackwise_demo_engine"]


def test_demo_inventory_sales_and_payments_pages_load(app, client):
    _enable_demo_database(app)
    entered = client.post(
        "/demo",
        data={"business_name": "Demo Operations Routes", "role": "admin"},
    )
    assert entered.status_code == 302

    for path, heading in (
        ("/inventory", b"Inventory Center"),
        ("/sales", b"Sales Checkout"),
        ("/payments", b"Payments Hub"),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert heading in response.data


def test_demo_admin_cannot_create_additional_users(app, client):
    demo_engine = _enable_demo_database(app)

    entered = client.post(
        "/demo",
        data={"business_name": "No Extra Users Demo", "role": "admin"},
    )
    assert entered.status_code == 302

    user_management = client.get("/users")
    assert user_management.status_code == 200
    assert b"Create User" not in user_management.data
    assert b'href="/users/create"' not in user_management.data

    assert client.get("/users/create").status_code == 404
    assert client.post(
        "/users/create",
        data={
            "name": "Extra Demo User",
            "email": "extra-demo@example.com",
            "password": "Example-pass-123!",
            "confirm_password": "Example-pass-123!",
            "role": "viewer",
        },
    ).status_code == 404

    with Session(demo_engine) as demo_session:
        users = demo_session.query(User).all()
        assert len(users) == 1
        assert users[0].role == "admin"


def test_existing_demo_business_offers_proceed_or_change(app, client):
    demo_engine = _enable_demo_database(app)

    first = client.post(
        "/demo",
        data={"business_name": "Acme Demo", "role": "viewer"},
    )
    assert first.status_code == 302
    with client.session_transaction() as session:
        first_user_id = int(session["_user_id"])

    existing = client.post(
        "/demo",
        data={"business_name": "  acme   demo ", "role": "manager"},
    )
    assert existing.status_code == 200
    assert b"This demo workspace exists" in existing.data
    assert b"Proceed to workspace" in existing.data
    assert b"Choose another business" in existing.data
    assert b'id="bottomNav"' not in existing.data

    with Session(demo_engine) as demo_session:
        assert demo_session.query(DemoWorkspace).count() == 1
        assert demo_session.query(User).count() == 1

    proceeded = client.post("/demo/proceed")
    assert proceeded.status_code == 302
    with client.session_transaction() as session:
        second_user_id = int(session["_user_id"])
    assert second_user_id != first_user_id

    with Session(demo_engine) as demo_session:
        users = demo_session.query(User).order_by(User.id).all()
        assert len(users) == 2
        assert {user.role for user in users} == {"viewer", "manager"}
        assert users[0].business_id == users[1].business_id
        assert users[0].email != users[1].email

    response = client.post(
        "/demo",
        data={"business_name": "Acme Demo", "role": "accountant"},
    )
    assert response.status_code == 200
    changed = client.post("/demo/change-business")
    assert changed.status_code == 302
    assert changed.headers["Location"].endswith("/demo")


def test_normal_credentials_switch_back_to_production_database(app, client):
    demo_engine = _enable_demo_database(app)
    production_user = app.test_client_user
    production_user_id = production_user.id
    production_email = production_user.email
    with app.app_context():
        production_user = db.session.get(User, production_user_id)
        production_user.set_password("Prod-test-Strong1!")
        db.session.commit()

    response = client.post(
        "/demo",
        data={"business_name": "Separate Demo", "role": "admin"},
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["_trackwise_database_context"] == "demo"

    response = client.post(
        "/login",
        data={
            "business_name": "Test Business",
            "email": production_email,
            "password": "Prod-test-Strong1!",
        },
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["_trackwise_database_context"] == "production"
        assert int(session["_user_id"]) == production_user_id

    with app.test_request_context("/"):
        from app.database import DatabaseRoutingSession

        routed_session = DatabaseRoutingSession(db)
        try:
            assert routed_session.get_bind() is db.engine
        finally:
            routed_session.close()

    with Session(demo_engine) as demo_session:
        assert demo_session.query(DemoWorkspace).count() == 1
