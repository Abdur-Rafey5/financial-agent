"""
Conversational assistant API.

The assistant is grounded in a deterministic financial snapshot. Gemini only
turns those facts into prose; if it is unavailable the endpoint returns a
factual backend-generated summary instead of inventing an answer.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.models.ai import AIConversation, AIMessage, MessageRole
from app.services import gemini
from app.services.financial_context import build_financial_context, context_to_prompt

router = APIRouter()

HISTORY_LIMIT = 10


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = None


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ChatResponse(BaseModel):
    conversation_id: str
    message: MessageItem
    ai_generated: bool
    context_period: str


class ConversationSummary(BaseModel):
    id: str
    title: Optional[str] = None
    message_count: int
    last_message: Optional[str] = None
    created_at: str
    updated_at: str


class ConversationDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    messages: List[MessageItem]
    created_at: str
    updated_at: str


async def _load_conversation(
    conversation_id: str, user_id: uuid.UUID, db
) -> AIConversation:
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = await db.scalar(
        select(AIConversation)
        .options(selectinload(AIConversation.messages))
        .where(and_(AIConversation.id == cid, AIConversation.user_id == user_id))
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _message_item(message: AIMessage) -> MessageItem:
    return MessageItem(
        id=str(message.id),
        role=message.role.value if hasattr(message.role, "value") else str(message.role),
        content=message.content,
        created_at=message.created_at.isoformat(),
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    payload: ChatMessageRequest, user: CurrentUser, db: DbSession
):
    """Send a message to the grounded financial assistant."""
    conversation: Optional[AIConversation] = None
    history: List[dict[str, str]] = []
    if payload.conversation_id:
        conversation = await _load_conversation(payload.conversation_id, user.id, db)
        history = [
            {
                "role": message.role.value
                if hasattr(message.role, "value")
                else str(message.role),
                "content": message.content,
            }
            for message in conversation.messages[-HISTORY_LIMIT:]
            if message.role != MessageRole.SYSTEM
        ]

    if conversation is None:
        conversation = AIConversation(
            user_id=user.id,
            title=payload.message.strip()[:60] or "New conversation",
        )
        db.add(conversation)
        await db.flush()

    db.add(
        AIMessage(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=payload.message.strip(),
        )
    )

    context = await build_financial_context(db, user)
    context_block = context_to_prompt(context)
    currency = context["user"]["currency"]
    user_category = context["user"]["category"]

    ai_generated = False
    try:
        reply = await gemini.generate_reply(
            system_prompt=gemini.build_system_prompt(context_block, currency),
            message=payload.message.strip(),
            history=history,
        )
        ai_generated = True
    except gemini.GeminiUnavailable:
        reply = gemini.fallback_reply(payload.message, context_block)

    assistant_message = AIMessage(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=reply,
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    return ChatResponse(
        conversation_id=str(conversation.id),
        message=_message_item(assistant_message),
        ai_generated=ai_generated,
        context_period=f"{context['period']['month_start']} to {context['period']['month_end']}",
    )


@router.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
):
    """List previous assistant conversations (newest first)."""
    result = await db.execute(
        select(AIConversation)
        .options(selectinload(AIConversation.messages))
        .where(AIConversation.user_id == user.id)
        .order_by(AIConversation.updated_at.desc())
        .limit(limit)
    )
    conversations = result.scalars().all()
    return [
        ConversationSummary(
            id=str(conversation.id),
            title=conversation.title,
            message_count=len(conversation.messages),
            last_message=conversation.messages[-1].content[:140]
            if conversation.messages
            else None,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
        )
        for conversation in conversations
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str, user: CurrentUser, db: DbSession):
    """Get a conversation with its full message history."""
    conversation = await _load_conversation(conversation_id, user.id, db)
    return ConversationDetailResponse(
        id=str(conversation.id),
        title=conversation.title,
        messages=[_message_item(message) for message in conversation.messages],
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
    )


@router.delete(
    "/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_conversation(conversation_id: str, user: CurrentUser, db: DbSession):
    """Delete a conversation and all of its messages."""
    conversation = await _load_conversation(conversation_id, user.id, db)
    await db.delete(conversation)
    await db.commit()
