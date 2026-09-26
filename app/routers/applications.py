from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import ApplicationStatus, InternshipApplication, Role, Student, User
from app.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
    StatusUpdate,
)


router = APIRouter(prefix="/applications", tags=["applications"])


def _get_application_or_404(
    application_id: int, db: Session
) -> InternshipApplication:
    application = db.get(InternshipApplication, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship application not found",
        )
    return application


def _check_application_access(
    application: InternshipApplication, user: User
) -> None:
    if user.role != Role.admin and application.student.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own applications",
        )


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an internship application",
    description=(
        "Students create an application for their own profile (student_id is "
        "inferred). Admins may create an application for any student by "
        "supplying student_id."
    ),
)
def create_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.student_id is None:
        if user.student is None:
            raise HTTPException(status_code=400, detail="Student profile not found")
        student_id = user.student.id
    elif user.role == Role.admin:
        student_id = payload.student_id
    else:
        if user.student is None or payload.student_id != user.student.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create applications for your own profile",
            )
        student_id = payload.student_id

    if db.get(Student, student_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    application = InternshipApplication(
        student_id=student_id,
        company_name=payload.company_name,
        role_title=payload.role_title,
        applied_date=payload.applied_date,
        notes=payload.notes,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.get(
    "",
    response_model=list[ApplicationResponse],
    summary="List internship applications",
    description=(
        "Admins see all applications and can filter by student. Students see "
        "only their own applications. Supports filtering by status, student "
        "(admin only), and applied_date range, plus text search by company "
        "name or role title."
    ),
)
def list_applications(
    search: Optional[str] = Query(
        default=None,
        description="Search company name and role title (case-insensitive)",
    ),
    application_status: Optional[ApplicationStatus] = Query(
        default=None, alias="status", description="Filter by application status"
    ),
    student_id: Optional[int] = Query(
        default=None, description="Filter by student (admin only)"
    ),
    date_from: Optional[date] = Query(
        default=None,
        description="Only applications with applied_date on/after this date",
    ),
    date_to: Optional[date] = Query(
        default=None,
        description="Only applications with applied_date on/before this date",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be on or before date_to",
        )

    statement = select(InternshipApplication)

    if user.role == Role.admin:
        if student_id is not None:
            statement = statement.where(
                InternshipApplication.student_id == student_id
            )
    else:
        if user.student is None:
            raise HTTPException(status_code=400, detail="Student profile not found")
        statement = statement.where(
            InternshipApplication.student_id == user.student.id
        )

    if search and (search_term := search.strip()):
        search_pattern = f"%{search_term}%"
        statement = statement.where(
            or_(
                InternshipApplication.company_name.ilike(search_pattern),
                InternshipApplication.role_title.ilike(search_pattern),
            )
        )

    if application_status is not None:
        statement = statement.where(
            InternshipApplication.status == application_status
        )
    if date_from is not None:
        statement = statement.where(InternshipApplication.applied_date >= date_from)
    if date_to is not None:
        statement = statement.where(InternshipApplication.applied_date <= date_to)

    statement = statement.order_by(InternshipApplication.id)
    return db.scalars(statement).all()


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get an internship application by ID",
    description="Admins can fetch any application. Students can only fetch their own.",
)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    application = _get_application_or_404(application_id, db)
    _check_application_access(application, user)
    return application


@router.patch(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Update an internship application",
    description=(
        "Partially update an application's details. Admins can update any "
        "application. Students can only update their own."
    ),
)
@router.put(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Replace an internship application's details",
    description=(
        "Update an application's details. Admins can update any application. "
        "Students can only update their own."
    ),
)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    application = _get_application_or_404(application_id, db)
    _check_application_access(application, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(application, field, value)

    db.commit()
    db.refresh(application)
    return application

@router.patch(
    "/{application_id}/status",
    response_model=ApplicationResponse,
    summary="Update an application's status",
    description="Admin only. Set status to pending, accepted, or rejected.",
)
def update_application_status(
    application_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    application = _get_application_or_404(application_id, db)
    application.status = payload.status
    db.commit()
    db.refresh(application)
    return application


@router.delete(
    "/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an internship application",
    description="Admin only.",
)
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    application = _get_application_or_404(application_id, db)
    db.delete(application)
    db.commit()