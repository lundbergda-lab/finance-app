"""Ekonomi — Family Finance Dashboard backend.

FastAPI + SQLite. Serves the single-page frontend from static/,
persists the app's DATA object, and proxies Anthropic API calls so
the API key never has to live in the browser.
"""
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

app = FastAPI(title="Ekonomi", docs_url=None, redoc_url=None)


@app.on_event("startup")
def startup() -> None:
    db.init_db()


def _server_api_key() -> str:
    return (os.getenv("ANTHROPIC_API_KEY") or "").strip()


def _effective_api_key() -> str:
    """Server .env key wins; the key saved in Settings is the fallback."""
    key = _server_api_key()
    if key:
        return key
    stored = db.get_setting("apiKey")
    return (stored or "").strip()


@app.get("/api/data")
def get_data():
    return {"data": db.load_data(), "hasServerKey": bool(_server_api_key())}


@app.put("/api/data")
@app.post("/api/data")  # POST alias so navigator.sendBeacon can flush on page close
async def put_data(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    db.save_data(payload)
    return {"ok": True}


@app.post("/api/anthropic/messages")
async def anthropic_proxy(request: Request):
    key = _effective_api_key()
    if not key:
        raise HTTPException(
            status_code=400,
            detail="No API key configured. Set ANTHROPIC_API_KEY in .env "
                   "or enter a key in Settings.")
    body = await request.json()
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            ANTHROPIC_API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            json=body,
        )
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
