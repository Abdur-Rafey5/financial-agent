"""
Authentication API: register, login, logout, and current-user info.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserBrief"


class UserBrief(BaseModel):
    id: str
    email: str
    full_name: str
    has_profile: bool

    model_config = {"from_attributes": True}


# ── Routes ───────────────────────────────────────────────────────────────
@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DbSession):
    """Create a new user account."""
    # Check if email is already registered
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()  # Get the user.id before commit

    token = create_access_token(subject=str(user.id))

    return AuthResponse(
        access_token=token,
        user=UserBrief(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            has_profile=False,
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: DbSession):
    """Authenticate with email and password."""
    result = await db.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(subject=str(user.id))

    return AuthResponse(
        access_token=token,
        user=UserBrief(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            has_profile=user.profile is not None,
        ),
    )


@router.post("/logout")
async def logout():
    """
    Logout the current user.

    With stateless JWT, logout is handled client-side by discarding the
    token. This endpoint exists for API completeness and future token
    blacklisting.
    """
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserBrief)
async def get_current_user_info(user: CurrentUser):
    """Return the authenticated user's basic information."""
    return UserBrief(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        has_profile=user.profile is not None,
    )
