"""Test configuration.

Runs the app against an isolated `ragbot_test` database in offline `fake` mode,
so the suite needs no OpenAI/Gemini credentials and never touches real data.

IMPORTANT: environment is set BEFORE any `app.*` import so pydantic-settings and
the SQLAlchemy engine pick up the test values.
"""
import os

# ---- Force test settings before the app is imported ----
os.environ["AI_PROVIDER"] = "fake"
os.environ["EMBEDDING_DIM"] = "32"  # small vectors keep the suite fast
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "adminpass123"
os.environ["OPENAI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

_BASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/ragbot"
)
_SERVER = _BASE_URL.rsplit("/", 1)[0]
_TEST_URL = f"{_SERVER}/ragbot_test"
os.environ["DATABASE_URL"] = _TEST_URL

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _ensure_test_database() -> None:
    """Create ragbot_test if it doesn't exist, then wipe its schema for a clean run."""
    server_engine = create_engine(f"{_SERVER}/postgres", isolation_level="AUTOCOMMIT")
    with server_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'ragbot_test'")
        ).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE ragbot_test"))
    server_engine.dispose()

    test_engine = create_engine(_TEST_URL, isolation_level="AUTOCOMMIT")
    with test_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    test_engine.dispose()


@pytest.fixture(scope="session")
def client():
    _ensure_test_database()
    from app.main import app

    # Entering the context runs the lifespan: init_db (extension + tables) + seed_admin.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_between_tests(client):
    """Reset data after each test, keeping the seeded admin user."""
    yield
    from app.database import SessionLocal

    with SessionLocal() as db:
        db.execute(
            text(
                "TRUNCATE messages, conversations, document_chunks, documents "
                "RESTART IDENTITY CASCADE"
            )
        )
        db.execute(text("DELETE FROM users WHERE email <> :email"), {"email": ADMIN_EMAIL})
        db.commit()


# ---- Shared helpers ----
def login(client, email: str, password: str) -> str:
    resp = client.post(
        "/api/auth/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def admin_token(client) -> str:
    return login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
