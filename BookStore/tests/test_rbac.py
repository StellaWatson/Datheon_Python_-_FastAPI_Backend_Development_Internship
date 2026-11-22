from tests.conftest import create_book


def test_new_user_has_user_role(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)
    assert response.json()["role"] == "user"


def test_admin_routes_require_token(client):
    assert client.get("/admin/users").status_code == 401


def test_regular_user_forbidden_from_admin(client, auth_headers):
    response = client.get("/admin/users", headers=auth_headers)
    assert response.status_code == 403


def test_admin_can_list_users(client, admin_headers, auth_headers):
    response = client.get("/admin/users", headers=admin_headers)
    assert response.status_code == 200
    emails = {u["email"] for u in response.json()}
    assert emails == {"admin@example.com", "user@example.com"}


def test_admin_can_promote_user(client, admin_headers, auth_headers):
    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]

    response = client.patch(
        f"/admin/users/{user_id}/role",
        json={"role": "admin"},
        headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    # The promoted user's existing token now grants admin access.
    assert client.get("/admin/users", headers=auth_headers).status_code == 200


def test_admin_cannot_demote_self(client, admin_headers):
    admin_id = client.get("/auth/me", headers=admin_headers).json()["id"]
    response = client.patch(
        f"/admin/users/{admin_id}/role",
        json={"role": "user"},
        headers=admin_headers
    )
    assert response.status_code == 400


def test_invalid_role_rejected(client, admin_headers, auth_headers):
    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    response = client.patch(
        f"/admin/users/{user_id}/role",
        json={"role": "superuser"},
        headers=admin_headers
    )
    assert response.status_code == 422


def test_deactivated_user_is_locked_out(client, admin_headers, auth_headers):
    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]

    response = client.patch(
        f"/admin/users/{user_id}/active",
        json={"is_active": False},
        headers=admin_headers
    )
    assert response.status_code == 200
    assert client.get("/auth/me", headers=auth_headers).status_code == 401


def test_admin_stats_join(client, admin_headers, auth_headers):
    create_book(client, auth_headers, price=10.0)
    create_book(client, auth_headers, price=15.5)

    response = client.get("/admin/stats", headers=admin_headers)
    assert response.status_code == 200
    stats = {row["username"]: row for row in response.json()}
    assert stats["test_user"]["book_count"] == 2
    assert stats["test_user"]["total_value"] == 25.5
    assert stats["admin"]["book_count"] == 0
