"""
AI service — analyses each contact submission with Claude.

In a single call it produces a structured analysis:
  • sentiment      (positive / neutral / negative)
  • category       (support / sales / hiring / feedback / spam / other)
  • priority       (low / medium / high)
  • summary        (one sentence)
  • suggested_reply (a draft the owner can send back)

Reliability is the priority: the call is bounded by a timeout and uses Claude
*tool use* with a forced `tool_choice` — the model must call our `record_triage`
tool, so its `input` comes back as a schema-shaped object (no brittle free-text
JSON parsing). If the API key is missing, the request times out, or anything
else goes wrong, the service degrades to a deterministic rule-based fallback so
the endpoint never fails because of the AI step.
"""
from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.models.schemas import (
    AIAnalysis,
    ContactRequest,
    Priority,
    RequestCategory,
    Sentiment,
)

logger = logging.getLogger("app.ai")

# A single tool whose input schema *is* our analysis contract. Forcing the model
# to call it (tool_choice) yields a parsed, schema-shaped `input` object — the
# structured-output pattern that works across all Claude models and SDK versions.
_TRIAGE_TOOL = {
    "name": "record_triage",
    "description": "Record the triage analysis of an inbound contact message.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": [s.value for s in Sentiment],
                "description": "Overall emotional tone of the message.",
            },
            "category": {
                "type": "string",
                "enum": [c.value for c in RequestCategory],
                "description": "The kind of request this message represents.",
            },
            "priority": {
                "type": "string",
                "enum": [p.value for p in Priority],
                "description": "How urgently the owner should respond.",
            },
            "summary": {
                "type": "string",
                "description": "One-sentence summary of the message.",
            },
            "suggested_reply": {
                "type": "string",
                "description": "A short, warm, professional draft reply to the sender.",
            },
        },
        "required": ["sentiment", "category", "priority", "summary", "suggested_reply"],
    },
}

_SYSTEM_PROMPT = (
    "You are the triage assistant for a freelance software developer's contact "
    "form. For each inbound message you classify sentiment, assign a request "
    "category and priority, summarise it in one sentence, and draft a short, "
    "warm, professional reply the developer can send back. Treat obvious spam "
    "or marketing solicitations as category 'spam' with low priority. Never "
    "invent facts about the developer; keep the reply generic and courteous."
)


class AIService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None
        if settings.ai_configured:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
                logger.info("AI service ready (model=%s)", settings.ai_model)
            except Exception as exc:  # pragma: no cover - import/env issues
                logger.error("Failed to init Anthropic client, using fallback: %s", exc)
        else:
            logger.warning("AI not configured — analysis will use rule-based fallback.")

    @property
    def available(self) -> bool:
        return self._client is not None

    async def analyze(self, submission: ContactRequest) -> AIAnalysis:
        """Analyse a submission, always returning a valid AIAnalysis."""
        if self._client is None:
            return self._fallback(submission, reason="not_configured")

        try:
            return await asyncio.wait_for(
                self._analyze_with_claude(submission),
                timeout=self._settings.ai_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("AI analysis timed out after %ss — falling back",
                           self._settings.ai_timeout_seconds)
            return self._fallback(submission, reason="timeout")
        except Exception as exc:  # network, API, parsing — never bubble up
            logger.error("AI analysis failed (%s) — falling back", exc)
            return self._fallback(submission, reason="error")

    async def _analyze_with_claude(self, submission: ContactRequest) -> AIAnalysis:
        user_content = (
            f"Name: {submission.name}\n"
            f"Email: {submission.email}\n"
            f"Phone: {submission.phone or 'n/a'}\n"
            f"Message:\n{submission.comment}"
        )
        response = await self._client.messages.create(
            model=self._settings.ai_model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=[_TRIAGE_TOOL],
            tool_choice={"type": "tool", "name": _TRIAGE_TOOL["name"]},
            messages=[{"role": "user", "content": user_content}],
        )
        # Forcing the tool guarantees a tool_use block whose `input` is already a
        # dict shaped like our schema — no free-text JSON parsing required.
        tool_use = next(b for b in response.content if b.type == "tool_use")
        data = tool_use.input
        logger.info(
            "AI analysis ok: sentiment=%s category=%s priority=%s",
            data["sentiment"], data["category"], data["priority"],
        )
        return AIAnalysis(
            sentiment=Sentiment(data["sentiment"]),
            category=RequestCategory(data["category"]),
            priority=Priority(data["priority"]),
            summary=data["summary"].strip(),
            suggested_reply=data["suggested_reply"].strip(),
            ai_available=True,
            model=self._settings.ai_model,
        )

    # ── Deterministic fallback ─────────────────────────────────────
    _NEG_WORDS = {
        "bad", "terrible", "awful", "hate", "angry", "broken", "bug", "issue",
        "problem", "disappointed", "refund", "worst", "slow", "error", "fail",
    }
    _POS_WORDS = {
        "great", "love", "awesome", "excellent", "amazing", "thanks", "thank",
        "good", "wonderful", "impressed", "perfect", "best", "fantastic",
    }
    _SPAM_WORDS = {"seo", "crypto", "casino", "loan", "viagra", "backlink", "bitcoin"}
    _HIRE_WORDS = {"hire", "job", "role", "position", "salary", "recruit", "contract"}
    _SALES_WORDS = {"project", "quote", "budget", "collaborat", "proposal", "build"}

    def _fallback(self, submission: ContactRequest, *, reason: str) -> AIAnalysis:
        text = submission.comment.lower()
        words = set(text.replace(",", " ").replace(".", " ").split())

        if self._SPAM_WORDS & words:
            category, priority = RequestCategory.spam, Priority.low
        elif self._HIRE_WORDS & words:
            category, priority = RequestCategory.hiring, Priority.high
        elif self._SALES_WORDS & {w[:9] for w in words}:
            category, priority = RequestCategory.sales, Priority.high
        else:
            category, priority = RequestCategory.other, Priority.medium

        neg = len(self._NEG_WORDS & words)
        pos = len(self._POS_WORDS & words)
        if neg > pos:
            sentiment = Sentiment.negative
            if category not in (RequestCategory.spam,):
                priority = Priority.high
        elif pos > neg:
            sentiment = Sentiment.positive
        else:
            sentiment = Sentiment.neutral

        logger.info("Fallback analysis used (reason=%s)", reason)
        return AIAnalysis(
            sentiment=sentiment,
            category=category,
            priority=priority,
            summary=(
                f"{submission.name} sent a {sentiment.value} message "
                f"categorised as {category.value}."
            ),
            suggested_reply=(
                f"Hi {submission.name.split()[0]}, thank you for reaching out — "
                "I've received your message and will get back to you shortly."
            ),
            ai_available=False,
            model=None,
        )
