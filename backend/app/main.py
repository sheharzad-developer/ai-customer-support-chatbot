from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, run_migrations
from app.models import User
from app.routers import auth, chat, documents
from app.security import hash_password


def seed_admin() -> None:
    """Create the seed admin user from settings if it does not exist yet."""
    with SessionLocal() as db:
        existing = db.execute(
            select(User).where(User.email == settings.admin_email)
        ).scalar_one_or_none()
        if existing:
            return
        db.add(
            User(
                email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password),
                is_admin=True,
            )
        )
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    seed_admin()
    yield


app = FastAPI(title="AI Customer Support Chatbot (RAG)", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
