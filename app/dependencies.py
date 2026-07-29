from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.config import Settings
from app.repositories.log_repository import SubmissionLogRepository
from app.repositories.metrics_repository import MetricsRepository
from app.services.ai_service import AIService
from app.services.contact_service import ContactService
from app.services.email_service import EmailService
from app.services.rate_limiter import RateLimiter


@dataclass
class Container:
    settings: Settings
    rate_limiter: RateLimiter
    ai_service: AIService
    email_service: EmailService
    log_repository: SubmissionLogRepository
    metrics_repository: MetricsRepository
    contact_service: ContactService


def build_container(settings: Settings) -> Container:
    data = settings.data_path
    logs = SubmissionLogRepository(data / "submissions.jsonl")
    metrics = MetricsRepository(data / "metrics.json")
    ai = AIService(settings)
    email = EmailService(settings)
    rate_limiter = RateLimiter(
        data / "rate_limit.json",
        settings.rate_limit_max_requests,
        settings.rate_limit_window_seconds,
    )
    contact = ContactService(ai=ai, email=email, logs=logs, metrics=metrics)
    return Container(
        settings=settings,
        rate_limiter=rate_limiter,
        ai_service=ai,
        email_service=email,
        log_repository=logs,
        metrics_repository=metrics,
        contact_service=contact,
    )


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_contact_service(request: Request) -> ContactService:
    return request.app.state.container.contact_service


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.container.rate_limiter


def get_metrics_repository(request: Request) -> MetricsRepository:
    return request.app.state.container.metrics_repository
