"""
User profile and onboarding API.

A profile is created exactly once by onboarding and then editable through the
settings screen. Updating settings never requires re-onboarding.
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models.user import UserCategory, UserProfile

router = APIRouter()

VALID_FREQUENCIES = {"weekly", "biweekly", "monthly", "quarterly", "yearly"}


# ── Schemas ──────────────────────────────────────────────────────────────
class ProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    category: Optional[str] = None
    currency: str = "PKR"
    onboarding_completed: bool = False
    allowance_amount: Optional[float] = None
    allowance_frequency: Optional[str] = None
    monthly_salary: Optional[float] = None
    employer_name: Optional[str] = None


class OnboardingRequest(BaseModel):
    category: str = Field(description="One of: student, employee, businessman")
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    allowance_amount: Optional[Decimal] = Field(default=None, ge=0)
    allowance_frequency: Optional[str] = Field(default=None, max_length=20)
    monthly_salary: Optional[Decimal] = Field(default=None, ge=0)
    employer_name: Optional[str] = Field(default=None, max_length=255)


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    allowance_amount: Optional[Decimal] = Field(default=None, ge=0)
    allowance_frequency: Optional[str] = Field(default=None, max_length=20)
    monthly_salary: Optional[Decimal] = Field(default=None, ge=0)
    employer_name: Optional[str] = Field(default=None, max_length=255)


def _parse_category(value: str) -> UserCategory:
    try:
        return UserCategory(value.strip().lower())
    except (ValueError, AttributeError):
        allowed = ", ".join(category.value for category in UserCategory)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid category. Must be one of: {allowed}",
        )


def _validate_frequency(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in VALID_FREQUENCIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"allowance_frequency must be one of: {', '.join(sorted(VALID_FREQUENCIES))}",
        )
    return normalized


def _profile_response(user, profile: Optional[UserProfile]) -> ProfileResponse:
    return ProfileResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        category=profile.category.value
        if profile and hasattr(profile.category, "value")
        else None,
        currency=profile.currency if profile else "PKR",
        onboarding_completed=profile.onboarding_completed if profile else False,
        allowance_amount=float(profile.allowance_amount)
        if profile and profile.allowance_amount is not None
        else None,
        allowance_frequency=profile.allowance_frequency if profile else None,
        monthly_salary=float(profile.monthly_salary)
        if profile and profile.monthly_salary is not None
        else None,
        employer_name=profile.employer_name if profile else None,
    )


# ── Routes ───────────────────────────────────────────────────────────────
@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(user: CurrentUser):
    """Get the current user's full profile."""
    return _profile_response(user, user.profile)


@router.post("/onboarding", response_model=ProfileResponse)
@router.post("/me/onboarding", response_model=ProfileResponse)
async def complete_onboarding(
    body: OnboardingRequest, user: CurrentUser, db: DbSession
):
    """Complete onboarding by selecting a category and entering profile info."""
    category = _parse_category(body.category)
    frequency = _validate_frequency(body.allowance_frequency)

    profile = await db.scalar(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    if profile is None:
        profile = UserProfile(user_id=user.id, category=category)
        db.add(profile)

    profile.category = category
    profile.currency = body.currency.upper()
    profile.onboarding_completed = True
    profile.allowance_amount = body.allowance_amount
    profile.allowance_frequency = frequency
    profile.monthly_salary = body.monthly_salary
    profile.employer_name = body.employer_name

    await db.commit()
    await db.refresh(profile)
    return _profile_response(user, profile)


@router.patch("/me", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdateRequest, user: CurrentUser, db: DbSession
):
    """Update the current user's profile and settings."""
    fields = body.model_fields_set
    profile = user.profile

    if body.full_name is not None:
        user.full_name = body.full_name.strip()

    profile_fields = {
        "category",
        "currency",
        "allowance_amount",
        "allowance_frequency",
        "monthly_salary",
        "employer_name",
    }
    if profile is None and fields & profile_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before updating financial settings",
        )

    if profile is not None:
        if body.category is not None:
            profile.category = _parse_category(body.category)
        if body.currency is not None:
            profile.currency = body.currency.upper()
        if "allowance_amount" in fields:
            profile.allowance_amount = body.allowance_amount
        if "allowance_frequency" in fields:
            profile.allowance_frequency = _validate_frequency(body.allowance_frequency)
        if "monthly_salary" in fields:
            profile.monthly_salary = body.monthly_salary
        if "employer_name" in fields:
            profile.employer_name = body.employer_name

    await db.commit()
    await db.refresh(user)
    if profile is not None:
        await db.refresh(profile)
    return _profile_response(user, profile)
