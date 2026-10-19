"""
A/B Testing API routes
----------------------
  GET /api/ab/results     - A/B test assignment counts
  GET /api/ab/experiments - Current experiment configuration
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/ab", tags=["ab_testing"])


@router.get("/results", summary="Get A/B test results")
def ab_results() -> dict:
    from backend.core.ab_testing import get_ab_manager
    return get_ab_manager().get_results()


@router.get("/experiments", summary="Get current A/B test configuration")
def ab_experiments() -> dict:
    from backend.core.ab_testing import get_ab_manager
    return {"experiments": get_ab_manager().get_experiments()}
