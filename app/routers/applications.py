from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import InternshipApplication, Role, Student, User
from app.schemas import ApplicationCreate, ApplicationResponse, ApplicationUpdate


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


@router.get("", response_model=list[ApplicationResponse])
def list_applications(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    statement = select(InternshipApplication).order_by(InternshipApplication.id)
    return db.scalars(statement).all()


@router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    application = _get_application_or_404(application_id, db)
    _check_application_access(application, user)
    return application


@router.patch("/{application_id}", response_model=ApplicationResponse)
@router.put("/{application_id}", response_model=ApplicationResponse)
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


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    application = _get_application_or_404(application_id, db)
    db.delete(application)
    db.commit()
