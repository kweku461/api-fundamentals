# Internship & Student Management API

Zaptek Backend Engineering with FastAPI, Team 2, Week 2.

A REST API where students register, manage their profile and track their internship
applications, and admins manage all students and decide each application's status.

**Live API:** `https://<your-service>.onrender.com/docs` *(replace once deployed)*

**Stack:** FastAPI · SQLAlchemy 2.0 · Pydantic v2 · JWT (PyJWT) + bcrypt · PostgreSQL on Render (SQLite locally) · pytest

---

## Features

- **Authentication:** register and log in with JWT bearer tokens; passwords are stored as bcrypt hashes
- **Authorization:** two roles. Students only reach their own profile and applications; admins reach everything
- **Students CRUD:** create, read, update and delete student profiles
- **Applications CRUD:** internship applications linked to a student (one student → many applications)
- **Search & filtering:** search applications by company or role, and filter by status, student and date range
- **Status updates:** admins move applications between `pending`, `accepted` and `rejected`
- **Consistent errors:** every error returns the same JSON shape with the right status code
- **Swagger docs:** interactive documentation at `/docs`

## Project structure

```
app/
  main.py           app setup, error handlers, admin creation, health check
  database.py       database connection and session
  models.py         User, Student and InternshipApplication tables
  schemas.py        request/response validation (Pydantic)
  security.py       password hashing and JWT tokens
  dependencies.py   get_current_user and require_admin
  routers/
    auth.py           register, login, me
    students.py       students CRUD
    applications.py   applications CRUD, search, filters, status
tests/
  test_api.py              auth, roles, CRUD, search and status
  test_error_handling.py   error shapes and validation
render.yaml         Render deployment blueprint
requirements.txt
.env.example
```

## Data model

| Table | Key columns |
|---|---|
| `users` | email (unique), hashed_password, role (`student` / `admin`) |
| `students` | full_name, email (unique), programme, level, user_id → users |
| `internship_applications` | student_id → students, company_name, role_title, status, applied_date, notes |

- **User → Student** is one-to-one: the login account is separate from the student's details.
  Changing a student's profile email also changes the email they log in with.
- Emails are stored in lowercase, so `Ama@x.com` and `ama@x.com` are the same address.
- **Student → Applications** is one-to-many. Deleting a student also deletes their applications.
- New applications start as `pending`.

## Run it locally

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

# optional: create an admin account on startup
export ADMIN_EMAIL=admin@example.com       # Windows PowerShell: $env:ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD=adminpass123         # Windows PowerShell: $env:ADMIN_PASSWORD="adminpass123"

uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs.

Settings are read from environment variables (see `.env.example`). Without `DATABASE_URL`,
the app uses a local SQLite file.

## Using the API in Swagger

1. `POST /auth/register` to create a student account (this also creates the student profile).
2. Click **Authorize** and log in with your **email in the `username` field** and your password.
3. Call any endpoint; the token is sent for you.

Public sign-up always gives the `student` role. The admin account is created at startup from
`ADMIN_EMAIL` and `ADMIN_PASSWORD`, so nobody can make themselves an admin.

## Endpoints

### Auth
| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/auth/register` | anyone | Create a student account and profile |
| POST | `/auth/login` | anyone | Get a JWT token (email goes in `username`) |
| GET | `/auth/me` | logged in | The current user |

### Students
| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/students` | logged in | Create a profile (a student can have only one) |
| GET | `/students` | admin | List all students |
| GET | `/students/{id}` | owner / admin | Get one student |
| PUT / PATCH | `/students/{id}` | owner / admin | Update a student (only the fields sent) |
| DELETE | `/students/{id}` | admin | Delete a student and their applications |

### Internship applications
| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/applications` | logged in | Create an application (students: for their own profile; admins must send `student_id`) |
| GET | `/applications` | logged in | List, search and filter (see below) |
| GET | `/applications/{id}` | owner / admin | Get one application |
| PUT / PATCH | `/applications/{id}` | owner / admin | Update application details |
| PATCH | `/applications/{id}/status` | admin | Set `pending`, `accepted` or `rejected` |
| DELETE | `/applications/{id}` | admin | Delete an application |

### Search and filters on `GET /applications`

All optional, and they can be combined:

| Parameter | Description |
|---|---|
| `search` | Matches company name or role title (case-insensitive) |
| `status` | `pending`, `accepted` or `rejected` |
| `student_id` | One student's applications (admin only) |
| `date_from` | Applied on or after this date (`YYYY-MM-DD`) |
| `date_to` | Applied on or before this date (`YYYY-MM-DD`) |

Example: `GET /applications?status=pending&search=gas&date_from=2026-09-01`

Students only ever see their own applications.

## Error responses

Every error has the same shape:

```json
{ "detail": "Internship application not found", "errors": [] }
```

Validation errors list each problem:

```json
{
  "detail": "Request validation failed",
  "errors": [
    { "location": ["body", "email"], "message": "value is not a valid email address", "type": "value_error" }
  ]
}
```

| Code | Meaning |
|---|---|
| 400 | Bad request |
| 401 | Not logged in, or invalid/expired token |
| 403 | Logged in but not allowed |
| 404 | Record not found |
| 409 | Conflict, e.g. email already registered |
| 422 | Input failed validation, or `date_from` is after `date_to` |
| 500 | Server error (details are logged, never shown) |

## Tests

```bash
pytest -v
```

Each test runs against a fresh in-memory SQLite database, so no setup is needed and your local
`internship.db` is not touched.

## Deploy on Render

1. On Render, choose **New → Blueprint** and select this repo. `render.yaml` creates the web service and a PostgreSQL database,
   and connects them (`DATABASE_URL` is filled in for you).
2. When asked, set `ADMIN_EMAIL` and `ADMIN_PASSWORD`. `SECRET_KEY` is generated automatically.
3. After the deploy, open `https://<your-service>.onrender.com/docs`.

Render checks `GET /` to confirm the service is running. On the free plan the service sleeps after
about 15 minutes idle, so the first request afterwards can take 30–60 seconds.

## Team

| Member | Contribution |
|---|---|
| Henry | Database models and schemas, project setup, deployment |
| Mensah Justice | JWT authentication |
| Bryan Owusu | Role-based access control |
| Sanker | Students CRUD |
| Joseph Boafo | Internship applications CRUD |
| Nana Kweku | Search and filtering, Swagger docs |
| Donkor | Application status updates |
| Agnes | Error handling and validation |
| Chris | Testing and presentation |
