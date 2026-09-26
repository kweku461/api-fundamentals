from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import Role, Student, User
from app.schemas import StudentCreate, StudentResponse, StudentUpdate


router = APIRouter(prefix="/students", tags=["students"])


def _get_student_or_404(student_id: int, db: Session) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    return student


def _check_student_access(student: Student, user: User) -> None:
    if user.role != Role.admin and student.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own student profile",
        )


def _ensure_email_available(email: str, db: Session, student_id: int | None = None) -> None:
    statement = select(Student).where(Student.email == email)
    existing = db.scalar(statement)
    if existing is not None and existing.id != student_id:
        raise HTTPException(status_code=409, detail="A student with this email already exists")


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_email_available(str(payload.email), db)

    if user.role == Role.student:
        if user.student is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A student profile already exists for this user",
            )
        user_id = user.id
    else:
        user_id = None

    student = Student(**payload.model_dump(), user_id=user_id)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("", response_model=list[StudentResponse])
def list_students(
    user: User = Depends(require_admin), db: Session = Depends(get_db)
):
    statement = select(Student).order_by(Student.id)
    return db.scalars(statement).all()


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    student = _get_student_or_404(student_id, db)
    _check_student_access(student, user)
    return student


@router.patch("/{student_id}", response_model=StudentResponse)
@router.put("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    student = _get_student_or_404(student_id, db)
    _check_student_access(student, user)

    values = payload.model_dump(exclude_unset=True)
    if "email" in values:
        _ensure_email_available(str(values["email"]), db, student.id)
    for field, value in values.items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    student = _get_student_or_404(student_id, db)
    db.delete(student)
    db.commit()
