from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

_PHONE_RE = re.compile(r"^\+?[\d ()\-]{7,20}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LINE_BREAKS = re.compile(r"[\r\n\t]+")


def _clean_text(value: str) -> str:
    return _CONTROL_CHARS.sub("", value).strip()


def _clean_line(value: str) -> str:
    return _LINE_BREAKS.sub(" ", _CONTROL_CHARS.sub("", value)).strip()


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


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Ada Lovelace"])
    email: EmailStr = Field(..., examples=["ada@example.com"])
    phone: Optional[str] = Field(default=None, max_length=20, examples=["+1 (555) 123-4567"])
    comment: str = Field(..., min_length=10, max_length=2000)

    @field_validator("name")
    @classmethod
    def _sanitise_name(cls, value: str) -> str:
        cleaned = _clean_line(value)
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("comment")
    @classmethod
    def _sanitise_comment(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = _clean_line(value)
        if cleaned == "":
            return None
        if not _PHONE_RE.match(cleaned):
            raise ValueError("must be a valid phone number (7–20 digits)")
        return cleaned


class AIAnalysis(BaseModel):
    sentiment: Sentiment
    category: RequestCategory
    priority: Priority
    summary: str
    suggested_reply: str
    ai_available: bool
    model: Optional[str] = None


class EmailDeliveryStatus(BaseModel):
    owner_notified: bool
    user_notified: bool
    mode: str


class ContactResponse(BaseModel):
    success: bool = True
    id: str
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
