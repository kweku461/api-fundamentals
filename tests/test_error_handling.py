from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import Role, User


def make_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)


def make_client_with_database():
    engine, session_factory = make_database()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    admin = User(
        id=1,
        email="admin@example.com",
        hashed_password="not-used",
        role=Role.admin,
    )
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin
    return TestClient(app, raise_server_exceptions=False), engine, session_factory


def test_update_rejects_null_for_required_fields():
    client, engine, _ = make_client_with_database()
    try:
        response = client.patch("/students/1", json={"email": None})
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"
    assert response.json()["errors"][0]["location"] == ["body", "email"]


def test_application_update_rejects_null_for_required_fields():
    client, engine, _ = make_client_with_database()
    try:
        response = client.patch("/applications/1", json={"applied_date": None})
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_reversed_application_date_range_returns_validation_error():
    client, engine, _ = make_client_with_database()
    try:
        response = client.get(
            "/applications?date_from=2026-09-20&date_to=2026-09-19"
        )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "date_from must be on or before date_to",
        "errors": [],
    }


def test_not_found_response_uses_standard_error_shape():
    client, engine, _ = make_client_with_database()
    try:
        response = client.get("/applications/999")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Internship application not found",
        "errors": [],
    }


def test_duplicate_registration_returns_conflict():
    client, engine, session_factory = make_client_with_database()
    db = session_factory()
    db.add(
        User(
            email="existing@example.com",
            hashed_password="not-used",
            role=Role.student,
        )
    )
    db.commit()
    db.close()

    try:
        response = client.post(
            "/auth/register",
            json={
                "email": "existing@example.com",
                "password": "password123",
                "full_name": "Existing Student",
            },
        )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Email is already registered",
        "errors": [],
    }


def test_database_and_unexpected_errors_do_not_expose_details():
    from sqlalchemy.exc import IntegrityError

    test_app = FastAPI()
    test_app.add_exception_handler(
        IntegrityError, app.exception_handlers[IntegrityError]
    )
    test_app.add_exception_handler(Exception, app.exception_handlers[Exception])

    @test_app.get("/integrity")
    def raise_integrity_error():
        raise IntegrityError("secret SQL", {}, Exception("secret database detail"))

    @test_app.get("/unexpected")
    def raise_unexpected_error():
        raise RuntimeError("secret internal detail")

    client = TestClient(test_app, raise_server_exceptions=False)
    integrity_response = client.get("/integrity")
    unexpected_response = client.get("/unexpected")

    assert integrity_response.status_code == 409
    assert integrity_response.json() == {
        "detail": "The request conflicts with existing data.",
        "errors": [],
    }
    assert unexpected_response.status_code == 500
    assert unexpected_response.json() == {
        "detail": "Internal server error",
        "errors": [],
    }