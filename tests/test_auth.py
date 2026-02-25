import pytest


def test_register(client):
    response = client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "secret123",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["role"] == "user"
    assert "hashed_password" not in data


def test_register_duplicate_username(client):
    client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup1@example.com",
        "password": "secret123",
    })
    response = client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup2@example.com",
        "password": "secret123",
    })
    assert response.status_code == 400


def test_register_duplicate_email(client):
    client.post("/auth/register", json={
        "username": "user1",
        "email": "shared@example.com",
        "password": "secret123",
    })
    response = client.post("/auth/register", json={
        "username": "user2",
        "email": "shared@example.com",
        "password": "secret123",
    })
    assert response.status_code == 400


def test_login(client):
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "secret123",
    })
    response = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "secret123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "username": "badpassuser",
        "email": "badpass@example.com",
        "password": "secret123",
    })
    response = client.post("/auth/login", data={
        "username": "badpassuser",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_me(client):
    client.post("/auth/register", json={
        "username": "meuser",
        "email": "me@example.com",
        "password": "secret123",
    })
    login = client.post("/auth/login", data={
        "username": "meuser",
        "password": "secret123",
    })
    token = login.json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "meuser"


def test_me_no_token(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
