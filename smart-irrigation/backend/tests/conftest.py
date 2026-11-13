import os
os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["JWT_SECRET"] = "test-only-signing-key-for-agripulse-tests-0001"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from app.database.base import Base
from app.database.init_db import init_db
from app.database.session import build_engine, get_db
from app.models import Farmer, User
from app.main import app
from app.services.auth_service import create_access_token


def owner_auth_headers(client, farmer_id):
    session_factory = client.test_session_factory
    with session_factory() as session:
        farmer = session.get(Farmer, farmer_id)
        if farmer is None:
            raise AssertionError(f"Test farmer {farmer_id} must exist before field registration.")
        if not farmer.email:
            farmer.email = f"field-owner-{uuid4().hex}@example.test"
            session.commit()
        user = session.query(User).filter(User.email == farmer.email).first()
        if user is None:
            user = User(
                full_name=farmer.name,
                email=farmer.email,
                hashed_password="test-token-only",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def post_field_as_owner(client, payload, **kwargs):
    headers = kwargs.pop("headers", None) or owner_auth_headers(client, payload["farmer_id"])
    return client.post("/fields", json=payload, headers=headers, **kwargs)


@pytest.fixture()
def engine():
    # In-memory SQLite by default; set TEST_DATABASE_URL to run the same tests on PostgreSQL.
    import os
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        eng = build_engine(url)
        Base.metadata.drop_all(eng)
    else:
        eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        from sqlalchemy import event

        @event.listens_for(eng, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    init_db(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db(engine):
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture()
def client(engine):
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        s = maker()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    # Not using `with TestClient(...)`: the lifespan would init the real configured DB.
    test_client = TestClient(app)
    test_client.test_session_factory = maker
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded(client):
    """Farmer Harini -> Field F001 (Rice, with coordinates) -> Sensor SM001."""
    client.post("/farmers", json={"farmer_id": "FR001", "name": "Harini", "phone": "9999900000"})
    post_field_as_owner(client, {
        "field_id": "F001", "farmer_id": "FR001", "name": "North Paddy",
        "location_name": "Hyderabad, Telangana", "latitude": 17.385, "longitude": 78.4867,
        "crop_type": "rice", "area_hectares": 1.5,
    })
    client.post("/sensors", json={"sensor_id": "SM001", "field_id": "F001"})
    return {"farmer": "FR001", "field": "F001", "sensor": "SM001"}
