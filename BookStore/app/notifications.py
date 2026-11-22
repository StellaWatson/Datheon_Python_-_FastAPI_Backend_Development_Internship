"""
Background jobs run with FastAPI BackgroundTasks.

They execute after the response has been sent, so the client never waits
for the email or webhook. Each finished job is recorded in an in-memory
log that admins can read at GET /admin/notifications.

- send_welcome_email: simulated email delivery (logged, not really sent).
- dispatch_webhook:   real HTTP POST to WEBHOOK_URL, with retries and
                      exponential backoff. Skipped if WEBHOOK_URL is unset.
"""
import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings


logger = logging.getLogger("bookstore.notifications")

# Most recent 100 finished jobs, newest last.
notification_log: deque[dict[str, Any]] = deque(maxlen=100)


def _record(
    kind: str,
    target: str,
    event: str,
    status: str,
    attempts: int,
    payload: dict[str, Any],
    detail: str | None = None
) -> None:
    notification_log.append({
        "kind": kind,
        "target": target,
        "event": event,
        "status": status,
        "attempts": attempts,
        "detail": detail,
        "payload": payload,
        "finished_at": datetime.now(timezone.utc)
    })


async def send_welcome_email(email: str, username: str) -> None:
    payload = {
        "subject": "Welcome to BookStore!",
        "body": f"Hi {username}, your account is ready. Happy reading!"
    }

    # Stand-in for an SMTP / email-provider call.
    await asyncio.sleep(0.1)

    logger.info("Welcome email sent to %s", email)
    _record("email", email, "user.registered", "sent", 1, payload)


async def dispatch_webhook(event: str, data: dict[str, Any]) -> None:
    url = settings.WEBHOOK_URL
    payload = {
        "event": event,
        "data": data,
        "sent_at": datetime.now(timezone.utc).isoformat()
    }

    if not url:
        _record("webhook", "-", event, "skipped", 0, payload,
                "WEBHOOK_URL is not configured")
        return

    last_error = None

    async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
        for attempt in range(1, settings.WEBHOOK_MAX_RETRIES + 1):
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                logger.info("Webhook %s delivered to %s", event, url)
                _record("webhook", url, event, "delivered", attempt, payload,
                        f"HTTP {response.status_code}")
                return

            except httpx.HTTPError as error:
                last_error = f"{type(error).__name__}: {error}"
                logger.warning("Webhook %s attempt %d failed: %s",
                               event, attempt, last_error)

                if attempt < settings.WEBHOOK_MAX_RETRIES:
                    await asyncio.sleep(0.5 * 2 ** (attempt - 1))

    _record("webhook", url, event, "failed",
            settings.WEBHOOK_MAX_RETRIES, payload, last_error)
