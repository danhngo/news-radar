"""FastAPI web dashboard."""

from __future__ import annotations

from pathlib import Path

import markdown
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import PROJECT_ROOT, get_config
from .. import db

app = FastAPI(title="AI Intelligence Radar")

WEB_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=WEB_DIR / "templates")


@app.on_event("startup")
async def startup():
    db.init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    briefings = db.get_briefings()
    source_counts = db.get_signal_counts_by_source()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "briefings": briefings,
        "source_counts": source_counts,
    })


@app.get("/briefing/{date}", response_class=HTMLResponse)
async def briefing(request: Request, date: str):
    cfg = get_config()
    briefings_dir = PROJECT_ROOT / cfg.get("briefings_dir", "briefings")
    md_file = briefings_dir / f"{date}.md"

    if not md_file.exists():
        return templates.TemplateResponse("briefing.html", {
            "request": request,
            "date": date,
            "content": "<p>Briefing not found.</p>",
        })

    md_content = md_file.read_text()
    html_content = markdown.markdown(md_content, extensions=["tables", "fenced_code"])

    return templates.TemplateResponse("briefing.html", {
        "request": request,
        "date": date,
        "content": html_content,
    })
