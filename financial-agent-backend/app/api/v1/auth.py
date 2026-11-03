"""
Authentication API: register, login, demo login, logout and current user.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.core.seed import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_account
from app.core.security import create_access_token, hash_password, verify_password
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


class UserBrief(BaseModel):
    id: str
    email: str
    full_name: str
    has_profile: bool


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBrief


def _user_brief(user: User) -> UserBrief:
    # ``profile`` is loaded eagerly on login/me. On a freshly flushed user it is
    # simply not in ``__dict__`` yet and must not trigger a lazy load in async code.
    profile = user.__dict__.get("profile")
    return UserBrief(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        has_profile=profile is not None,
    )


async def _load_user_by_email(db, email: str) -> User | None:
    return await db.scalar(
        select(User).options(selectinload(User.profile)).where(User.email == email)
    )


# ── Routes ───────────────────────────────────────────────────────────────
@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(body: RegisterRequest, db: DbSession):
    """Create a new user account and return an access token."""
    existing = await _load_user_by_email(db, body.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name.strip(),
    )
    db.add(user)
    await db.flush()

    return AuthResponse(
        access_token=create_access_token(subject=str(user.id)),
        user=_user_brief(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: DbSession):
    """Authenticate with email and password."""
    user = await _load_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return AuthResponse(
        access_token=create_access_token(subject=str(user.id)),
        user=_user_brief(user),
    )


@router.post("/demo", response_model=AuthResponse)
async def demo_login(db: DbSession):
    """
    Sign in to the read-only-ish demo account.

    The account is created on first use with a month of deterministic sample
    data so the product can be explored without registering.
    """
    user = await _load_user_by_email(db, DEMO_EMAIL)
    if user is None:
        created = await seed_demo_account(db)
        if created is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Demo account is not available",
            )
        user = await _load_user_by_email(db, DEMO_EMAIL)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Demo account could not be created",
            )

    return AuthResponse(
        access_token=create_access_token(subject=str(user.id)),
        user=_user_brief(user),
    )


@router.get("/demo/credentials")
async def demo_credentials():
    """Expose the demo credentials so the sign-in screen can prefill them."""
    return {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}


@router.post("/logout")
async def logout():
    """Stateless JWT logout; the client discards the token."""
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserBrief)
async def get_current_user_info(user: CurrentUser):
    """Return the authenticated user's basic information."""
    return _user_brief(user)
