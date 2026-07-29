from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.models.schemas import AIAnalysis, ContactRequest, ContactResponse
from app.repositories.log_repository import SubmissionLogRepository
from app.repositories.metrics_repository import MetricsRepository
from app.services.ai_service import AIService
from app.services.email_service import EmailService

logger = logging.getLogger("app.contact")


class ContactService:
    def __init__(
        self,
        ai: AIService,
        email: EmailService,
        logs: SubmissionLogRepository,
        metrics: MetricsRepository,
    ):
        self._ai = ai
        self._email = email
        self._logs = logs
        self._metrics = metrics

    async def handle_submission(
        self, submission: ContactRequest, *, client_ip: str
    ) -> ContactResponse:
        submission_id = uuid.uuid4().hex[:16]
        logger.info("Processing submission %s from %s", submission_id, submission.email)

        analysis: AIAnalysis = await self._ai.analyze(submission)

        email_status = await self._email.send_submission_emails(
            submission, analysis, submission_id
        )
        emails_ok = email_status.owner_notified and email_status.user_notified

        await self._logs.append(
            {
                "id": submission_id,
                "client_ip": client_ip,
                "name": submission.name,
                "email": submission.email,
                "phone": submission.phone,
                "comment": submission.comment,
                "analysis": analysis.model_dump(mode="json"),
                "email_status": email_status.model_dump(mode="json"),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        await self._metrics.record_submission(
            sentiment=analysis.sentiment.value,
            category=analysis.category.value,
            priority=analysis.priority.value,
            ai_success=analysis.ai_available,
            email_sent=emails_ok,
        )

        logger.info(
            "Submission %s done (ai=%s, emails=%s/%s)",
            submission_id, analysis.ai_available,
            email_status.owner_notified, email_status.user_notified,
        )
        return ContactResponse(
            id=submission_id, analysis=analysis, email=email_status
        )
