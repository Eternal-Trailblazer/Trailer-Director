"""Trailer Plan and Validation models."""

from __future__ import annotations

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from src.models.segment import Segment
from src.models.audience import AudiencePromise


class ValidationStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"
    REJECTED = "REJECTED"


class ValidationCheck(BaseModel):
    check_id: str
    check_type: str  # "spoiler", "rights", "source_accuracy", "audience_safety", etc.
    verdict: str  # "PASS" | "WARN" | "FAIL"
    evidence: list[str] = Field(default_factory=list)
    details: str = ""


class TrailerValidation(BaseModel):
    status: ValidationStatus
    checks: list[ValidationCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    human_approvals_required: list[str] = Field(default_factory=list)


class TrailerPlan(BaseModel):
    trailer_id: str
    audience: str
    audience_promise: AudiencePromise
    duration_seconds: float
    segments: list[Segment] = Field(default_factory=list)
    validation: Optional[TrailerValidation] = None
    estimated_cost: float = 0.0
    fallback_plan: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)
    human_approvals_pending: list[str] = Field(default_factory=list)