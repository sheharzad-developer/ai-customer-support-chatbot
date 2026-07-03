"""End-to-end RAG flow tests (offline fake mode): upload -> embed -> chat -> history."""
from tests.conftest import admin_token, auth_header, login

FAQ = b"Acme Corp support hours are 9am to 6pm Pacific Time, Monday through Friday."


def _upload(client, token, content=FAQ, title="FAQ"):
    return client.post(
        "/api/documents",
        headers=auth_header(token),
        files={"file": ("faq.txt", content, "text/plain")},
        data={"title": title},
    )


def test_admin_upload_and_list(client):
    token = admin_token(client)
    resp = _upload(client, token)
    assert resp.status_code == 201
    assert resp.json()["chunk_count"] >= 1

    listed = client.get("/api/documents", headers=auth_header(token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_non_admin_cannot_upload(client):
    client.post(
        "/api/auth/register",
        json={"email": "member@example.com", "password": "pw123456"},
    )
    token = login(client, "member@example.com", "pw123456")
    resp = _upload(client, token)
    assert resp.status_code == 403


def test_empty_file_rejected(client):
    token = admin_token(client)
    resp = _upload(client, token, content=b"")
    assert resp.status_code == 400


def test_chat_streams_and_persists_history(client):
    token = admin_token(client)
    _upload(client, token)

    with client.stream(
        "POST",
        "/api/chat",
        headers=auth_header(token),
        json={"message": "What are your support hours?"},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    # SSE frames we expect from the streaming endpoint.
    assert "event: meta" in body
    assert "event: token" in body
    assert "event: done" in body

    convos = client.get(
        "/api/chat/conversations", headers=auth_header(token)
    ).json()
    assert len(convos) == 1

    detail = client.get(
        f"/api/chat/conversations/{convos[0]['id']}", headers=auth_header(token)
    ).json()
    roles = [m["role"] for m in detail["messages"]]
    assert "user" in roles and "assistant" in roles


def test_delete_conversation(client):
    token = admin_token(client)
    with client.stream(
        "POST",
        "/api/chat",
        headers=auth_header(token),
        json={"message": "hello"},
    ) as resp:
        list(resp.iter_text())

    convos = client.get(
        "/api/chat/conversations", headers=auth_header(token)
    ).json()
    assert len(convos) == 1
    cid = convos[0]["id"]

    deleted = client.delete(
        f"/api/chat/conversations/{cid}", headers=auth_header(token)
    )
    assert deleted.status_code == 204

    convos_after = client.get(
        "/api/chat/conversations", headers=auth_header(token)
    ).json()
    assert convos_after == []


def test_cannot_access_others_conversation(client):
    # Admin starts a conversation.
    admin = admin_token(client)
    with client.stream(
        "POST", "/api/chat", headers=auth_header(admin), json={"message": "hi"}
    ) as resp:
        list(resp.iter_text())
    cid = client.get("/api/chat/conversations", headers=auth_header(admin)).json()[0][
        "id"
    ]

    # A different user must not be able to read it.
    client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "pw123456"},
    )
    other = login(client, "other@example.com", "pw123456")
    resp = client.get(
        f"/api/chat/conversations/{cid}", headers=auth_header(other)
    )
    assert resp.status_code == 404
