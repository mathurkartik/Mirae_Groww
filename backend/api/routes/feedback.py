"""
Feedback API routes
-------------------
  POST /api/feedback         - Submit user feedback
  GET  /api/feedback/summary - Aggregated feedback metrics
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    conversation_id: str = Field(..., description="Thread/conversation ID")
    message_id: str = Field(..., description="Message ID being rated")
    query: str = Field(..., description="Original user query")
    rating: str = Field(..., description="One of: helpful, not_helpful, incorrect, refused_wrongly")
    comment: Optional[str] = Field("", description="Optional user comment")


class FeedbackResponse(BaseModel):
    status: str
    entry: dict


@router.post("/feedback", response_model=FeedbackResponse, summary="Submit user feedback")
def submit_feedback(body: FeedbackRequest) -> dict:
    from backend.core.feedback import store_feedback, VALID_RATINGS

    if body.rating not in VALID_RATINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid rating. Must be one of: {sorted(VALID_RATINGS)}",
        )

    # Retrieve experiment assignments for this conversation if available
    from backend.core.ab_testing import get_ab_manager
    manager = get_ab_manager()
    assignments = manager.get_assignment(body.conversation_id)

    entry = store_feedback(
        conversation_id=body.conversation_id,
        message_id=body.message_id,
        query=body.query,
        rating=body.rating,
        comment=body.comment or "",
        experiment_assignments=assignments,
    )
    return {"status": "ok", "entry": entry}


@router.get("/feedback/summary", summary="Get feedback summary metrics")
def feedback_summary() -> dict:
    from backend.core.feedback import get_summary
    return get_summary()
