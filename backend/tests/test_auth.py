from tests.conftest import auth_header, login


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_login_me(client):
    reg = client.post(
        "/api/auth/register",
        json={"email": "user1@example.com", "password": "pw123456"},
    )
    assert reg.status_code == 201
    assert reg.json()["is_admin"] is False

    token = login(client, "user1@example.com", "pw123456")
    me = client.get("/api/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["email"] == "user1@example.com"


def test_duplicate_email_rejected(client):
    payload = {"email": "dupe@example.com", "password": "pw123456"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 400


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "user2@example.com", "password": "pw123456"},
    )
    resp = client.post(
        "/api/auth/login",
        data={"username": "user2@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_invalid_email_rejected(client):
    resp = client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": "pw"}
    )
    assert resp.status_code == 422


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401
