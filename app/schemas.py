# Owner: Henry (Phase 1 - Pydantic schemas)
# Validation rules added by Agnes (Phase 3 - validation)
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import ApplicationStatus, Role


def _not_in_future(value: date | None) -> date | None:
    if value is not None and value > date.today():
        raise ValueError("applied_date cannot be in the future")
    return value


def _reject_explicit_null(value: object) -> object:
    if value is None:
        raise ValueError("Field cannot be null")
    return value


# ---------- Auth / users ----------

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=150)
    programme: str | None = Field(default=None, max_length=150)
    level: int | None = Field(default=None, ge=100, le=900)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: Role
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Students ----------

class StudentBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    programme: str | None = Field(default=None, max_length=150)
    level: int | None = Field(default=None, ge=100, le=900)


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    # every field optional: only the fields that are sent get changed
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    programme: str | None = Field(default=None, max_length=150)
    level: int | None = Field(default=None, ge=100, le=900)

    _check_required_fields = field_validator(
        "full_name", "email", mode="before"
    )(_reject_explicit_null)


class StudentResponse(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    created_at: datetime


# ---------- Internship applications ----------

class ApplicationCreate(BaseModel):
    # students leave this out (their own profile is used);
    # admins must say which student the application is for
    student_id: int | None = None
    company_name: str = Field(min_length=1, max_length=150)
    role_title: str = Field(min_length=1, max_length=150)
    applied_date: date
    notes: str | None = Field(default=None, max_length=2000)

    _check_date = field_validator("applied_date")(_not_in_future)


class ApplicationUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=150)
    role_title: str | None = Field(default=None, min_length=1, max_length=150)
    applied_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    _check_required_fields = field_validator(
        "company_name", "role_title", "applied_date", mode="before"
    )(_reject_explicit_null)
    _check_date = field_validator("applied_date")(_not_in_future)


class StatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    company_name: str
    role_title: str
    status: ApplicationStatus
    applied_date: date
    notes: str | None
    created_at: datetime
    updated_at: datetime
