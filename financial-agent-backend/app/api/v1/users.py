"""
User profile and onboarding API.
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models.user import User, UserProfile, UserCategory

router = APIRouter()


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

    model_config = {"from_attributes": True}


class OnboardingRequest(BaseModel):
    category: str = Field(description="One of: student, employee, businessman")
    currency: str = Field(default="PKR", max_length=3)
    # Student fields
    allowance_amount: Optional[Decimal] = None
    allowance_frequency: Optional[str] = None
    # Employee fields
    monthly_salary: Optional[Decimal] = None
    employer_name: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    currency: Optional[str] = None
    allowance_amount: Optional[Decimal] = None
    allowance_frequency: Optional[str] = None
    monthly_salary: Optional[Decimal] = None
    employer_name: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────────────
@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(user: CurrentUser):
    """Get the current user's full profile."""
    profile = user.profile
    return ProfileResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        category=profile.category.value if profile else None,
        currency=profile.currency if profile else "PKR",
        onboarding_completed=profile.onboarding_completed if profile else False,
        allowance_amount=float(profile.allowance_amount) if profile and profile.allowance_amount else None,
        allowance_frequency=profile.allowance_frequency if profile else None,
        monthly_salary=float(profile.monthly_salary) if profile and profile.monthly_salary else None,
        employer_name=profile.employer_name if profile else None,
    )


@router.post("/onboarding", response_model=ProfileResponse, status_code=status.HTTP_200_OK)
@router.post("/me/onboarding", response_model=ProfileResponse, status_code=status.HTTP_200_OK)
async def complete_onboarding(body: OnboardingRequest, user: CurrentUser, db: DbSession):
    """Complete or update the onboarding process by selecting a category and entering profile info."""

    # Validate category
    try:
        category = UserCategory(body.category.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid category. Must be one of: {', '.join(c.value for c in UserCategory)}",
        )

    # Check for existing profile for this user
    res = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = res.scalar_one_or_none()

    if profile:
        profile.category = category
        profile.currency = body.currency
        profile.onboarding_completed = True
        profile.allowance_amount = body.allowance_amount
        profile.allowance_frequency = body.allowance_frequency
        profile.monthly_salary = body.monthly_salary
        profile.employer_name = body.employer_name
    else:
        profile = UserProfile(
            user_id=user.id,
            category=category,
            currency=body.currency,
            onboarding_completed=True,
            allowance_amount=body.allowance_amount,
            allowance_frequency=body.allowance_frequency,
            monthly_salary=body.monthly_salary,
            employer_name=body.employer_name,
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)

    return ProfileResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        category=category.value,
        currency=body.currency,
        onboarding_completed=True,
        allowance_amount=float(body.allowance_amount) if body.allowance_amount else None,
        allowance_frequency=body.allowance_frequency,
        monthly_salary=float(body.monthly_salary) if body.monthly_salary else None,
        employer_name=body.employer_name,
    )


@router.patch("/me", response_model=ProfileResponse)
async def update_profile(body: ProfileUpdateRequest, user: CurrentUser, db: DbSession):
    """Update the current user's profile."""
    if body.full_name is not None:
        user.full_name = body.full_name

    if user.profile:
        if body.currency is not None:
            user.profile.currency = body.currency
        if body.allowance_amount is not None:
            user.profile.allowance_amount = body.allowance_amount
        if body.allowance_frequency is not None:
            user.profile.allowance_frequency = body.allowance_frequency
        if body.monthly_salary is not None:
            user.profile.monthly_salary = body.monthly_salary
        if body.employer_name is not None:
            user.profile.employer_name = body.employer_name

    await db.flush()

    profile = user.profile
    return ProfileResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        category=profile.category.value if profile else None,
        currency=profile.currency if profile else "PKR",
        onboarding_completed=profile.onboarding_completed if profile else False,
        allowance_amount=float(profile.allowance_amount) if profile and profile.allowance_amount else None,
        allowance_frequency=profile.allowance_frequency if profile else None,
        monthly_salary=float(profile.monthly_salary) if profile and profile.monthly_salary else None,
        employer_name=profile.employer_name if profile else None,
    )
