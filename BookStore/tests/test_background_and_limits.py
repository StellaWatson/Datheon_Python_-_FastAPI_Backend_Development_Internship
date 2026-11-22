import httpx

from app.config import settings
from app.notifications import notification_log
from tests.conftest import create_book


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_queues_welcome_email(client, auth_headers):
    # TestClient runs background tasks before returning the response.
    emails = [n for n in notification_log if n["kind"] == "email"]
    assert len(emails) == 1
    assert emails[0]["target"] == "user@example.com"
    assert emails[0]["status"] == "sent"


def test_webhook_skipped_without_url(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_URL", None)
    create_book(client, auth_headers)

    hook = notification_log[-1]
    assert hook["event"] == "book.created"
    assert hook["status"] == "skipped"


def test_webhook_delivered(client, auth_headers, monkeypatch):
    received = []

    def handler(request: httpx.Request):
        received.append(request)
        return httpx.Response(200)

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(settings, "WEBHOOK_URL", "http://hooks.test/bookstore")

    create_book(client, auth_headers, title="Webhook Book")

    assert len(received) == 1
    hook = notification_log[-1]
    assert hook["status"] == "delivered"
    assert hook["payload"]["data"]["title"] == "Webhook Book"


def test_webhook_retries_then_fails(client, auth_headers, monkeypatch):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        return httpx.Response(500)

    _patch_httpx(monkeypatch, handler)
    monkeypatch.setattr(settings, "WEBHOOK_URL", "http://hooks.test/bookstore")
    monkeypatch.setattr(settings, "WEBHOOK_MAX_RETRIES", 2)

    create_book(client, auth_headers)

    assert len(calls) == 2
    assert notification_log[-1]["status"] == "failed"


def test_admin_can_view_notifications(client, admin_headers, auth_headers):
    response = client.get("/admin/notifications", headers=admin_headers)
    assert response.status_code == 200
    assert any(n["kind"] == "email" for n in response.json())


def test_login_rate_limited(client):
    payload = {"email": "nobody@example.com", "password": "wrongpass"}

    for _ in range(settings.AUTH_RATE_LIMIT):
        assert client.post("/auth/login", json=payload).status_code == 401

    response = client.post("/auth/login", json=payload)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_rate_limit_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    payload = {"email": "nobody@example.com", "password": "wrongpass"}

    for _ in range(settings.AUTH_RATE_LIMIT + 3):
        assert client.post("/auth/login", json=payload).status_code == 401


def _patch_httpx(monkeypatch, handler):
    """Route the webhook's AsyncClient through a MockTransport."""
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr("app.notifications.httpx.AsyncClient", factory)
    monkeypatch.setattr("app.notifications.asyncio.sleep", _no_sleep)


async def _no_sleep(_):
    return None
