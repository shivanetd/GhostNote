from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import connect_db, close_db
from app.routers import secrets as secrets_router

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="GhostNote",
    description=(
        "## Zero-Knowledge One-Time Secret Sharing\n\n"
        "Secrets are encrypted **in the browser** with AES-256-GCM before leaving your device. "
        "This server only ever receives unreadable ciphertext.\n\n"
        "The decryption key lives exclusively in the **URL fragment** (`#key`). "
        "Browsers never include the fragment in HTTP requests — the server is "
        "architecturally incapable of reading your secret.\n\n"
        "On first view, the ciphertext is atomically deleted via `find_one_and_delete()`. "
        "MongoDB's TTL index auto-purges unrevealed secrets after your chosen expiry time."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(secrets_router.router)

# Serve crypto.js and other static assets at /static/*
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/s/{secret_id}", include_in_schema=False)
async def view_secret_page(secret_id: str):
    # The decryption key arrives as the URL fragment (#key) — never in this path param
    return FileResponse(STATIC_DIR / "view.html")
