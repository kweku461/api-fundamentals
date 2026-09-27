import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import hash_password

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "adminpass123"


@pytest.fixture
def client():
    """A client backed by a fresh in-memory database, with one admin account."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    db = session_factory()
    db.add(User(email=ADMIN_EMAIL, hashed_password=hash_password(ADMIN_PASSWORD), role=Role.admin))
    db.commit()
    db.close()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, email, full_name="Test Student", password="password123"):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )


def login(client, email, password="password123"):
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.json()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def admin_headers(client):
    return login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def student(client, email):
    """Registers a student and returns (headers, student_id)."""
    assert register(client, email).status_code == 201
    students = client.get("/students", headers=admin_headers(client)).json()
    return login(client, email), next(s["id"] for s in students if s["email"] == email)


def create_application(client, headers, **overrides):
    body = {"company_name": "Ghana Gas", "role_title": "Backend Intern", "applied_date": "2026-09-01"}
    body.update(overrides)
    return client.post("/applications", headers=headers, json=body)


# ---------- health ----------

def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "docs": "/docs"}


# ---------- auth ----------

def test_register_creates_student_account_and_profile(client):
    response = register(client, "Ama@Example.com", full_name="Ama Mensah")
    assert response.status_code == 201
    assert response.json()["email"] == "ama@example.com"
    assert response.json()["role"] == "student"

    students = client.get("/students", headers=admin_headers(client)).json()
    assert students[0]["full_name"] == "Ama Mensah"
    assert students[0]["user_id"] == response.json()["id"]


def test_register_rejects_same_email_in_different_case(client):
    register(client, "ama@example.com")
    response = register(client, "AMA@example.com")
    assert response.status_code == 409


def test_login_and_me(client):
    register(client, "ama@example.com")
    headers = login(client, "AMA@example.com")
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "ama@example.com"


def test_login_with_wrong_password_is_rejected(client):
    register(client, "ama@example.com")
    response = client.post("/auth/login", data={"username": "ama@example.com", "password": "wrong-pass"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_missing_or_invalid_token_is_rejected(client):
    assert client.get("/applications").status_code == 401
    bad = client.get("/applications", headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401
    assert bad.json()["detail"] == "Invalid or expired token"


# ---------- students ----------

def test_only_admin_can_list_or_delete_students(client):
    headers, student_id = student(client, "ama@example.com")
    assert client.get("/students", headers=headers).status_code == 403
    assert client.delete(f"/students/{student_id}", headers=headers).status_code == 403
    assert client.delete(f"/students/{student_id}", headers=admin_headers(client)).status_code == 204
    assert client.get(f"/students/{student_id}", headers=admin_headers(client)).status_code == 404


def test_student_can_read_and_update_only_own_profile(client):
    ama, ama_id = student(client, "ama@example.com")
    _, kofi_id = student(client, "kofi@example.com")

    assert client.get(f"/students/{ama_id}", headers=ama).status_code == 200
    assert client.get(f"/students/{kofi_id}", headers=ama).status_code == 403

    response = client.patch(f"/students/{ama_id}", headers=ama, json={"programme": "Computer Engineering"})
    assert response.status_code == 200
    assert response.json()["programme"] == "Computer Engineering"
    assert response.json()["full_name"] == "Test Student"  # untouched
    assert client.patch(f"/students/{kofi_id}", headers=ama, json={"level": 300}).status_code == 403


def test_student_cannot_create_a_second_profile(client):
    ama, _ = student(client, "ama@example.com")
    response = client.post("/students", headers=ama, json={"full_name": "Ama Two", "email": "ama2@example.com"})
    assert response.status_code == 409


def test_student_emails_are_case_insensitive(client):
    admin = admin_headers(client)
    first = client.post("/students", headers=admin, json={"full_name": "Kofi", "email": "Kofi@Example.com"})
    assert first.status_code == 201
    assert first.json()["email"] == "kofi@example.com"
    second = client.post("/students", headers=admin, json={"full_name": "Kofi", "email": "kofi@example.com"})
    assert second.status_code == 409


def test_changing_profile_email_changes_login_email(client):
    ama, ama_id = student(client, "ama@example.com")
    response = client.patch(f"/students/{ama_id}", headers=ama, json={"email": "Ama.New@example.com"})
    assert response.status_code == 200
    assert response.json()["email"] == "ama.new@example.com"

    login(client, "ama.new@example.com")
    old = client.post("/auth/login", data={"username": "ama@example.com", "password": "password123"})
    assert old.status_code == 401


def test_profile_email_cannot_take_another_users_login_email(client):
    ama, ama_id = student(client, "ama@example.com")
    response = client.patch(f"/students/{ama_id}", headers=ama, json={"email": ADMIN_EMAIL})
    assert response.status_code == 409


# ---------- applications ----------

def test_student_creates_application_for_own_profile(client):
    ama, ama_id = student(client, "ama@example.com")
    response = create_application(client, ama)
    assert response.status_code == 201
    assert response.json()["student_id"] == ama_id
    assert response.json()["status"] == "pending"


def test_student_cannot_create_application_for_someone_else(client):
    ama, _ = student(client, "ama@example.com")
    _, kofi_id = student(client, "kofi@example.com")
    assert create_application(client, ama, student_id=kofi_id).status_code == 403


def test_admin_must_give_student_id(client):
    admin = admin_headers(client)
    response = create_application(client, admin)
    assert response.status_code == 422
    assert response.json()["detail"] == "student_id is required when an admin creates an application"

    _, ama_id = student(client, "ama@example.com")
    assert create_application(client, admin, student_id=ama_id).status_code == 201
    assert create_application(client, admin, student_id=9999).status_code == 404


def test_applied_date_cannot_be_in_the_future(client):
    ama, _ = student(client, "ama@example.com")
    response = create_application(client, ama, applied_date="2999-01-01")
    assert response.status_code == 422


def test_student_only_sees_and_edits_own_applications(client):
    ama, _ = student(client, "ama@example.com")
    kofi, _ = student(client, "kofi@example.com")
    application_id = create_application(client, ama).json()["id"]

    assert client.get(f"/applications/{application_id}", headers=kofi).status_code == 403
    assert client.get("/applications", headers=kofi).json() == []
    assert client.patch(f"/applications/{application_id}", headers=kofi, json={"notes": "x"}).status_code == 403

    response = client.patch(f"/applications/{application_id}", headers=ama, json={"notes": "Interview on Monday"})
    assert response.status_code == 200
    assert response.json()["notes"] == "Interview on Monday"
    assert response.json()["company_name"] == "Ghana Gas"  # untouched


def test_only_admin_can_change_status_or_delete(client):
    ama, _ = student(client, "ama@example.com")
    admin = admin_headers(client)
    application_id = create_application(client, ama).json()["id"]

    assert client.patch(f"/applications/{application_id}/status", headers=ama, json={"status": "accepted"}).status_code == 403
    response = client.patch(f"/applications/{application_id}/status", headers=admin, json={"status": "accepted"})
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

    bad = client.patch(f"/applications/{application_id}/status", headers=admin, json={"status": "maybe"})
    assert bad.status_code == 422

    assert client.delete(f"/applications/{application_id}", headers=ama).status_code == 403
    assert client.delete(f"/applications/{application_id}", headers=admin).status_code == 204
    assert client.get(f"/applications/{application_id}", headers=admin).status_code == 404


def test_deleting_student_deletes_their_applications(client):
    ama, ama_id = student(client, "ama@example.com")
    admin = admin_headers(client)
    create_application(client, ama)
    create_application(client, ama, company_name="MTN")

    assert client.delete(f"/students/{ama_id}", headers=admin).status_code == 204
    assert client.get("/applications", headers=admin).json() == []


def test_search_and_filters(client):
    ama, ama_id = student(client, "ama@example.com")
    kofi, kofi_id = student(client, "kofi@example.com")
    admin = admin_headers(client)

    gas = create_application(client, ama, company_name="Ghana Gas", applied_date="2026-09-01").json()
    create_application(client, ama, company_name="MTN", role_title="Data Intern", applied_date="2026-08-01")
    create_application(client, kofi, company_name="Hubtel", role_title="Gas Analyst", applied_date="2026-09-10")
    client.patch(f"/applications/{gas['id']}/status", headers=admin, json={"status": "accepted"})

    def companies(query, headers=admin):
        response = client.get(f"/applications{query}", headers=headers)
        assert response.status_code == 200
        return sorted(a["company_name"] for a in response.json())

    assert companies("") == ["Ghana Gas", "Hubtel", "MTN"]
    assert companies("?search=GAS") == ["Ghana Gas", "Hubtel"]  # company or role, any case
    assert companies("?status=accepted") == ["Ghana Gas"]
    assert companies(f"?student_id={kofi_id}") == ["Hubtel"]
    assert companies("?date_from=2026-09-01") == ["Ghana Gas", "Hubtel"]
    assert companies("?date_to=2026-08-31") == ["MTN"]
    assert companies("?search=gas&status=pending") == ["Hubtel"]

    # students never see other students' applications, even when asking for them
    assert companies("?search=gas", headers=ama) == ["Ghana Gas"]
    assert companies(f"?student_id={kofi_id}", headers=ama) == ["Ghana Gas", "MTN"]
