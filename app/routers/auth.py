# Owner: Mensah Justice (Phase 1 - JWT authentication)
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Role, Student, User
from app.schemas import Token, UserRegister, UserResponse
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Creates a login account **and** a matching student profile.
    Public sign-up always gives the `student` role; admins are created by the
    server from the ADMIN_EMAIL / ADMIN_PASSWORD settings."""
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=400, detail="Email is already registered")
    if db.scalar(select(Student).where(Student.email == email)):
        raise HTTPException(status_code=400, detail="A student with this email already exists")

    user = User(email=email, hashed_password=hash_password(data.password), role=Role.student)
    user.student = Student(
        full_name=data.full_name, email=email, programme=data.programme, level=data.level
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token, summary="Log in and get an access token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Send your email in the `username` field. Returns a JWT bearer token."""
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id, user.role.value))


@router.get("/me", response_model=UserResponse, summary="Get the logged-in user")
def me(user: User = Depends(get_current_user)):
    return user
