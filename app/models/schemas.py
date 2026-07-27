"""
Request/response schemas.

Pydantic v2 models double as the validation layer and the OpenAPI contract.
Input is validated *and* sanitised here (trimming, control-char stripping,
length bounds) so downstream services and the AI/email steps only ever see
clean data.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# Loose international phone check: optional +, then 7–20 digits/spaces/dashes/parens.
_PHONE_RE = re.compile(r"^\+?[0-9()\-\s]{7,20}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: str) -> str:
    """Strip control characters and collapse surrounding whitespace."""
    return _CONTROL_CHARS.sub("", value).strip()


# ── Domain enums (also used by the AI classifier) ──────────────────
class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class RequestCategory(str, Enum):
    support = "support"
    sales = "sales"
    hiring = "hiring"
    feedback = "feedback"
    spam = "spam"
    other = "other"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ── Inbound ────────────────────────────────────────────────────────
class ContactRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Ada Lovelace"])
    email: EmailStr = Field(..., examples=["ada@example.com"])
    phone: Optional[str] = Field(
        default=None, max_length=20, examples=["+1 (555) 123-4567"]
    )
    comment: str = Field(
        ..., min_length=10, max_length=2000,
        examples=["I loved your portfolio and would like to discuss a project."],
    )

    @field_validator("name", "comment")
    @classmethod
    def _sanitise_text(cls, value: str) -> str:
        cleaned = _clean(value)
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = _clean(value)
        if cleaned == "":
            return None
        if not _PHONE_RE.match(cleaned):
            raise ValueError("must be a valid phone number (7–20 digits)")
        return cleaned


# ── AI analysis result ─────────────────────────────────────────────
class AIAnalysis(BaseModel):
    sentiment: Sentiment
    category: RequestCategory
    priority: Priority
    summary: str = Field(..., description="One-sentence summary of the message.")
    suggested_reply: str = Field(
        ..., description="Draft reply the owner can send to the user."
    )
    ai_available: bool = Field(
        ..., description="False when the response came from the rule-based fallback."
    )
    model: Optional[str] = Field(
        default=None, description="AI model used, or null when falling back."
    )


# ── Outbound ───────────────────────────────────────────────────────
class EmailDeliveryStatus(BaseModel):
    owner_notified: bool
    user_notified: bool
    mode: str = Field(..., description='"smtp" for real delivery, "console" for dry-run.')


class ContactResponse(BaseModel):
    success: bool = True
    id: str = Field(..., description="Unique submission id.")
    message: str = "Thank you! Your message has been received."
    analysis: AIAnalysis
    email: EmailDeliveryStatus


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str
    uptime_seconds: float
    dependencies: dict[str, str]


class MetricsResponse(BaseModel):
    total_submissions: int
    ai_success: int
    ai_fallback: int
    emails_sent: int
    emails_failed: int
    by_sentiment: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]
    first_submission_at: Optional[str] = None
    last_submission_at: Optional[str] = None
