def test_register(client):
    user_data = {
        "username": "abdulloh",
        "email": "abdulloh@example.com",
        "password": "abdulloh1642"
    }
    response=client.post("/auth/register", json=user_data)
    assert response.status_code==201
    data=response.json()
    assert data["username"] =="abdulloh"
    assert data["email"]=="abdulloh@example.com"
    assert data["is_active"] is True
    assert "id" in data
    assert "password" not in data
    assert "hashed_password" not in data

def test_register_duplicate_email(client):
    user_data = {
        "username": "first_user",
        "email": "dupe@example.com",
        "password": "password123"
    }

    first = client.post("/auth/register", json=user_data)
    assert first.status_code == 201

    # Same email, different username: the email check must fire.
    user_data["username"] = "second_user"
    second = client.post("/auth/register", json=user_data)

    assert second.status_code == 409
    assert second.json()["detail"] == "Email is already registered"
def test_register_duplicate_username(client):
    user_data = {
        "username": "first_user",
        "email": "dupe@example.com",
        "password": "password123"
    }
    first =client.post("/auth/register", json=user_data)
    assert first.status_code==201
    user_data["email"]="second@gmail.com"
    
    second=client.post("/auth/register", json=user_data)
    
    assert second.status_code==409
    assert second.json()["detail"] == "Username is already taken"
    
def test_register_with_short_password(client):
    user_data = {
        "username": "first_user",
        "email": "dupe@example.com",
        "password": "stella"
    }
    response=client.post("/auth/register",json=user_data)
    
    assert response.status_code==422
    
def test_register_with_invalid_email(client):
    user_data = {
        "username": "first_user",
        "email": "dupeexample.com",
        "password": "stella2407"
    }
    
    response=client.post("/auth/register",json=user_data)
    
    assert response.status_code==422
def test_me_endpoint(client, auth_headers):
    response=client.get("/auth/me",
                        headers=auth_headers)
    assert response.status_code==200
    
    assert response.json()["email"]=="user@example.com"
    response2=client.get("/auth/me")
    assert response2.status_code==401