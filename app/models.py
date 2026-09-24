# Owner: Henry (Phase 1 - database models and relationships)
import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(str, enum.Enum):
    student = "student"
    admin = "admin"


class ApplicationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class User(Base):
    """A login account. Every student has one; admins have one too."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.student)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # one-to-one: a student user has one student profile
    student: Mapped["Student | None"] = relationship(back_populates="user", uselist=False)


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    programme: Mapped[str | None] = mapped_column(String(150), nullable=True)
    level: Mapped[int | None] = mapped_column(nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User | None"] = relationship(back_populates="student")
    # one-to-many: one student has many applications.
    # cascade means deleting a student also deletes their applications.
    applications: Mapped[list["InternshipApplication"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class InternshipApplication(Base):
    __tablename__ = "internship_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    company_name: Mapped[str] = mapped_column(String(150), index=True)
    role_title: Mapped[str] = mapped_column(String(150))
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.pending, index=True
    )
    applied_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    student: Mapped["Student"] = relationship(back_populates="applications")
