from tests.conftest import register_and_login, create_book
# -------------------------
# BOOKS: CRUD
# -------------------------

def test_get_books(client, auth_headers):
    response = client.get("/books", headers=auth_headers)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_book(client, auth_headers):
    book_data = {
        "title": "Clean Architecture",
        "author": "Robert C. Martin",
        "price": 35.0
    }

    response = client.post("/books", json=book_data, headers=auth_headers)

    assert response.status_code == 201

    data = response.json()
    assert data["title"] == book_data["title"]
    assert data["author"] == book_data["author"]
    assert data["price"] == book_data["price"]
    assert "id" in data


def test_get_specific_book(client, auth_headers):
    book_id = create_book(client, auth_headers, title="Test Book", author="Test Author", price=15.0)

    response = client.get(f"/books/{book_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == book_id
    assert response.json()["title"] == "Test Book"


def test_get_nonexistent_book(client, auth_headers):
    response = client.get("/books/999999", headers=auth_headers)

    assert response.status_code == 404


def test_put_books(client, auth_headers):
    book_id = create_book(client, auth_headers)

    updated_data = {
        "title": "Updated Book",
        "author": "Updated Author",
        "price": 20.0
    }

    response = client.put(f"/books/{book_id}", json=updated_data, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == book_id
    assert response.json()["title"] == "Updated Book"
    assert response.json()["author"] == "Updated Author"
    assert response.json()["price"] == 20.0


def test_delete_book(client, auth_headers):
    book_id = create_book(client, auth_headers, title="Book to Delete", price=12.0)

    delete_response = client.delete(f"/books/{book_id}", headers=auth_headers)
    assert delete_response.status_code == 200

    get_response = client.get(f"/books/{book_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_delete_nonexistent_book(client, auth_headers):
    response = client.delete("/books/999999", headers=auth_headers)

    assert response.status_code == 404


# -------------------------
# BOOKS: VALIDATION
# -------------------------

def test_create_book_invalid_price(client, auth_headers):
    book_data = {
        "title": "Invalid Book",
        "author": "Test Author",
        "price": -10
    }

    response = client.post("/books", json=book_data, headers=auth_headers)

    assert response.status_code == 422


def test_create_book_missing_author(client, auth_headers):
    book_data = {
        "title": "Book Without Author",
        "price": 15.0
    }

    response = client.post("/books", json=book_data, headers=auth_headers)

    assert response.status_code == 422


# -------------------------
# AUTH
# -------------------------

def test_books_without_token(client):
    response = client.get("/books")

    assert response.status_code == 401


def test_books_with_invalid_token(client):
    response = client.get(
        "/books",
        headers={"Authorization": "Bearer invalid"}
    )

    assert response.status_code == 401


def test_login_wrong_password(client, auth_headers):
    # auth_headers is requested only so that user@example.com exists.
    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrongpassword"}
    )

    assert response.status_code == 401


def test_login_wrong_email(client):
    response = client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "stringst"}
    )

    assert response.status_code == 401


# -------------------------
# OWNERSHIP
# -------------------------

def test_user_cannot_access_another_users_book(client, auth_headers, user_b_headers):
    book_id = create_book(client, auth_headers)

    response = client.get(f"/books/{book_id}", headers=user_b_headers)

    assert response.status_code == 404


def test_user_cannot_update_another_users_book(client, auth_headers, user_b_headers):
    book_id = create_book(client, auth_headers)

    response = client.put(
        f"/books/{book_id}",
        json={"title": "Hacked Book", "author": "Someone Else", "price": 99.0},
        headers=user_b_headers
    )
    assert response.status_code == 404

    # The owner still sees the original, untouched book.
    check_response = client.get(f"/books/{book_id}", headers=auth_headers)
    assert check_response.status_code == 200
    assert check_response.json()["title"] == "Old Book"


def test_user_cannot_delete_another_users_book(client, auth_headers, user_b_headers):
    book_id = create_book(client, auth_headers)

    response = client.delete(f"/books/{book_id}", headers=user_b_headers)
    assert response.status_code == 404

    check_response = client.get(f"/books/{book_id}", headers=auth_headers)
    assert check_response.status_code == 200
    assert check_response.json()["title"] == "Old Book"
def test_get_books_pagination(client, auth_headers):
    create_book(client, auth_headers, title="Book One", price=10.0)
    create_book(client, auth_headers, title="Book Two", price=20.0)
    create_book(client, auth_headers, title="Book Three", price=30.0)

    # First page: two books.
    first_page = client.get(
        "/books",
        params={"limit": 2},
        headers=auth_headers
    )
    assert first_page.status_code == 200
    assert len(first_page.json()) == 2

    # Second page: skip the first two, one book should remain.
    second_page = client.get(
        "/books",
        params={"skip": 2, "limit": 2},
        headers=auth_headers
    )
    assert second_page.status_code == 200
    assert len(second_page.json()) == 1

    # The leftover book must not be one we already saw on page one.
    first_page_ids = {book["id"] for book in first_page.json()}
    leftover_id = second_page.json()[0]["id"]
    assert leftover_id not in first_page_ids
def test_filtering_by_author(client, auth_headers):
    create_book(client, auth_headers, title="Book One", author="Robert C. Martin")
    create_book(client, auth_headers, title="Book Two", author="Martin Fowler")
    create_book(client, auth_headers, title="Book Three",author="Eric Matthes")

    first = client.get(
        "/books",
        params={"author": "martin"},
        headers=auth_headers
    )
    books = first.json()
    assert len(books) == 2
    assert all("martin" in book["author"].lower() for book in books)

    