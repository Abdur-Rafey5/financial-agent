"""
AI Conversational Assistant API — Gemini-powered financial advisor.
"""

import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import settings
from app.models.ai import AIConversation, AIMessage, MessageRole
from app.models.income import IncomeRecord
from app.models.expense import ExpenseRecord
from app.models.budget import Budget
from app.models.goal import FinancialGoal

router = APIRouter()


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: Optional[str] = None


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ChatResponse(BaseModel):
    conversation_id: str
    message: MessageItem


class ConversationDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    messages: List[MessageItem]
    created_at: str


async def _generate_gemini_response(user_category: str, prompt: str, user_context_str: str) -> str:
    """Call Google Gemini API if key is available, or use intelligent category-specific rules."""
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if api_key and api_key != "your-gemini-api-key-here":
        try:
            import httpx

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            system_instruction = (
                f"You are an expert AI Financial Advisor specializing in assisting {user_category.upper()} users. "
                "Provide precise, actionable financial wisdom, encouraging discipline, clear budgeting, and wealth creation. "
                f"User financial snapshot:\n{user_context_str}\n"
                "Keep answers crisp, encouraging, structured with bullet points where appropriate."
            )

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{system_instruction}\n\nUser Question: {prompt}"}
                        ]
                    }
                ]
            }

            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text:
                            return text
        except Exception:
            pass

    # High-quality fallback response generator
    cat_lower = user_category.lower()
    if cat_lower == "student":
        return (
            f"🎓 **Student Financial Guidance:**\n\n"
            f"Based on your query: *\"{prompt}\"*:\n\n"
            f"1. **Protect your essential buffer**: Keep at least 20-30% of your allowance for emergencies before spending on social activities.\n"
            f"2. **Daily Spending Limit**: Divide your disposable pocket money by the days left in the month to avoid running out early.\n"
            f"3. **Micro-Savings**: Even saving Rs. 100-500 weekly compounds good financial habits early.\n\n"
            f"Let me know if you would like me to adjust your budget allocations!"
        )
    elif cat_lower == "businessman":
        return (
            f"💼 **Business Financial Analysis:**\n\n"
            f"Regarding your inquiry: *\"{prompt}\"*:\n\n"
            f"1. **Working Capital Protection**: Maintain at least 3 to 6 months of fixed operational expenses in highly liquid accounts.\n"
            f"2. **Gross Margin vs Cash Flow**: Profitable sales that take 60+ days to collect can still strangle cash flow. Monitor your cash conversion cycle.\n"
            f"3. **ROI Stress Testing**: Before expanding or acquiring inventory, test scenarios under a 15% revenue downturn.\n\n"
            f"Would you like to model a what-if scenario in the Business module?"
        )
    else:  # employee
        return (
            f"💼 **Personal Wealth Strategy (Employee):**\n\n"
            f"Reviewing your question: *\"{prompt}\"*:\n\n"
            f"1. **50/30/20 Rule**: Direct 50% of your net salary toward needs, 30% to wants, and automate 20% into savings or long-term investments.\n"
            f"2. **Emergency Cushion**: Target 3-6 months of living expenses saved in high-yield or safe liquid funds.\n"
            f"3. **Milestone Tracking**: Prioritize funding active goals before increasing lifestyle expenses.\n\n"
            f"Shall we review your current month's budget limits?"
        )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(payload: ChatMessageRequest, user: CurrentUser, db: DbSession):
    """Interact with the financial assistant."""
    conv: Optional[AIConversation] = None
    if payload.conversation_id:
        try:
            cid = uuid.UUID(payload.conversation_id)
            res = await db.execute(
                select(AIConversation).where(
                    and_(AIConversation.id == cid, AIConversation.user_id == user.id)
                )
            )
            conv = res.scalar_one_or_none()
        except ValueError:
            pass

    if not conv:
        conv = AIConversation(
            user_id=user.id,
            title=payload.message[:50],
        )
        db.add(conv)
        await db.flush()

    # Save user message
    user_msg = AIMessage(
        conversation_id=conv.id,
        role=MessageRole.USER,
        content=payload.message,
    )
    db.add(user_msg)

    # Gather user context summary
    category_obj = user.profile.category if user.profile else None
    user_cat = category_obj.value if hasattr(category_obj, "value") else str(category_obj or "employee").lower()
    context_str = f"Category: {user_cat}, Email: {user.email}"

    # Generate assistant reply
    assistant_reply_text = await _generate_gemini_response(user_cat, payload.message, context_str)

    assistant_msg = AIMessage(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content=assistant_reply_text,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    return ChatResponse(
        conversation_id=str(conv.id),
        message=MessageItem(
            id=str(assistant_msg.id),
            role="assistant",
            content=assistant_msg.content,
            created_at=assistant_msg.created_at.isoformat(),
        ),
    )


@router.get("/conversations", response_model=List[ConversationDetailResponse])
async def list_conversations(user: CurrentUser, db: DbSession):
    """List previous AI assistant conversations."""
    res = await db.execute(
        select(AIConversation)
        .options(selectinload(AIConversation.messages))
        .where(AIConversation.user_id == user.id)
        .order_by(AIConversation.created_at.desc())
    )
    conversations = res.scalars().all()
    return [
        ConversationDetailResponse(
            id=str(c.id),
            title=c.title,
            messages=[
                MessageItem(
                    id=str(m.id),
                    role=m.role.value if hasattr(m.role, "value") else str(m.role),
                    content=m.content,
                    created_at=m.created_at.isoformat(),
                )
                for m in c.messages
            ],
            created_at=c.created_at.isoformat(),
        )
        for c in conversations
    ]
