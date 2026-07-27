"""
Email service.

Sends two messages per submission:
  1. a notification to the site owner (with the AI triage attached), and
  2. a confirmation copy to the user who submitted the form.

If SMTP isn't configured (no SMTP_HOST) the service runs in "console" mode:
the fully-rendered emails are logged instead of sent, so the whole request
pipeline still works end-to-end in development and on hosts without mail
credentials. Real SMTP failures are surfaced to the caller as delivery status
rather than crashing the request.
"""
from __future__ import annotations

import logging
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib

from app.config import Settings
from app.models.schemas import AIAnalysis, ContactRequest, EmailDeliveryStatus

logger = logging.getLogger("app.email")


class EmailService:
    def __init__(self, settings: Settings):
        self._s = settings
        self._mode = "smtp" if settings.email_configured else "console"
        if self._mode == "console":
            logger.warning("SMTP not configured — emails run in console (dry-run) mode.")

    async def send_submission_emails(
        self, submission: ContactRequest, analysis: AIAnalysis, submission_id: str
    ) -> EmailDeliveryStatus:
        owner_msg = self._build_owner_email(submission, analysis, submission_id)
        user_msg = self._build_user_email(submission, analysis)

        owner_ok = await self._deliver(owner_msg, label="owner")
        user_ok = await self._deliver(user_msg, label="user-copy")

        return EmailDeliveryStatus(
            owner_notified=owner_ok, user_notified=user_ok, mode=self._mode
        )

    # ── Delivery ───────────────────────────────────────────────────
    async def _deliver(self, message: EmailMessage, *, label: str) -> bool:
        if self._mode == "console":
            logger.info(
                "[console-email:%s] to=%s subject=%s\n%s",
                label, message["To"], message["Subject"],
                message.get_content(),
            )
            return True
        try:
            await aiosmtplib.send(
                message,
                hostname=self._s.smtp_host,
                port=self._s.smtp_port,
                username=self._s.smtp_user or None,
                password=self._s.smtp_password or None,
                start_tls=self._s.smtp_use_tls,
                use_tls=not self._s.smtp_use_tls and self._s.smtp_port == 465,
                timeout=15,
            )
            logger.info("Email delivered (%s) to %s", label, message["To"])
            return True
        except Exception as exc:  # SMTP/connection errors must not crash the request
            logger.error("Email delivery failed (%s) to %s: %s",
                         label, message["To"], exc)
            return False

    # ── Rendering ──────────────────────────────────────────────────
    def _from(self) -> str:
        return formataddr((self._s.smtp_from_name, self._s.smtp_from_email))

    def _build_owner_email(
        self, sub: ContactRequest, analysis: AIAnalysis, sid: str
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = self._from()
        msg["To"] = self._s.owner_email
        msg["Reply-To"] = sub.email
        msg["Subject"] = (
            f"[{analysis.priority.value.upper()}] New {analysis.category.value} "
            f"message from {sub.name}"
        )
        msg.set_content(
            f"New contact submission (id: {sid})\n"
            f"{'=' * 48}\n"
            f"Name    : {sub.name}\n"
            f"Email   : {sub.email}\n"
            f"Phone   : {sub.phone or 'n/a'}\n\n"
            f"Message :\n{sub.comment}\n\n"
            f"{'-' * 48}\n"
            f"AI triage ({'live' if analysis.ai_available else 'fallback'})\n"
            f"  Sentiment : {analysis.sentiment.value}\n"
            f"  Category  : {analysis.category.value}\n"
            f"  Priority  : {analysis.priority.value}\n"
            f"  Summary   : {analysis.summary}\n\n"
            f"Suggested reply:\n{analysis.suggested_reply}\n"
        )
        return msg

    def _build_user_email(
        self, sub: ContactRequest, analysis: AIAnalysis
    ) -> EmailMessage:
        first_name = sub.name.split()[0]
        msg = EmailMessage()
        msg["From"] = self._from()
        msg["To"] = sub.email
        msg["Subject"] = "Thanks for reaching out!"
        msg.set_content(
            f"Hi {first_name},\n\n"
            "Thanks for getting in touch — this is an automated confirmation "
            "that your message has been received. Here's a copy for your "
            "records:\n\n"
            f"{sub.comment}\n\n"
            "I'll get back to you as soon as I can.\n\n"
            f"Best regards,\n{self._s.smtp_from_name}\n"
        )
        return msg
