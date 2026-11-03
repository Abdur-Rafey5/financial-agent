"""Helpers for recording agent events that can trigger automated analysis."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AgentEvent


def log_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: Optional[dict[str, Any]] = None,
) -> AgentEvent:
    """
    Queue an agent event in the current session.

    The event is committed together with the mutation that caused it, so the
    automated recommendation worker never observes a partial state.
    """
    event = AgentEvent(
        user_id=user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        event_metadata=metadata or {},
        processed=False,
    )
    db.add(event)
    return event
