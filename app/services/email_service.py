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
        except Exception as exc:
            logger.error("Email delivery failed (%s) to %s: %s",
                         label, message["To"], exc)
            return False

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
            f"[{analysis.priority.value.upper()}] Новое обращение "
            f"({analysis.category.value}) от {sub.name}"
        )
        msg.set_content(
            f"Новое обращение с формы (id: {sid})\n"
            f"{'=' * 48}\n"
            f"Имя       : {sub.name}\n"
            f"Email     : {sub.email}\n"
            f"Телефон   : {sub.phone or '—'}\n\n"
            f"Сообщение :\n{sub.comment}\n\n"
            f"{'-' * 48}\n"
            f"AI-разбор ({'рабочий' if analysis.ai_available else 'запасной'})\n"
            f"  Тональность : {analysis.sentiment.value}\n"
            f"  Категория   : {analysis.category.value}\n"
            f"  Приоритет   : {analysis.priority.value}\n"
            f"  Резюме      : {analysis.summary}\n\n"
            f"Черновик ответа:\n{analysis.suggested_reply}\n"
        )
        return msg

    def _build_user_email(
        self, sub: ContactRequest, analysis: AIAnalysis
    ) -> EmailMessage:
        first_name = sub.name.split()[0]
        msg = EmailMessage()
        msg["From"] = self._from()
        msg["To"] = sub.email
        msg["Subject"] = "Спасибо за обращение!"
        msg.set_content(
            f"Здравствуйте, {first_name}!\n\n"
            "Спасибо, что написали — это автоматическое подтверждение, что ваше "
            "сообщение получено. Копия для вас:\n\n"
            f"{sub.comment}\n\n"
            "Я свяжусь с вами в ближайшее время.\n\n"
            f"С уважением,\n{self._s.smtp_from_name}\n"
        )
        return msg
