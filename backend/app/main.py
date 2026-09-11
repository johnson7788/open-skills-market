from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .data import get_skill_by_slug, list_categories, store_payload
from .auth import get_optional_user
from .agent.chat import manager
from .routers.auth_router import router as auth_router
from .routers.chat_router import router as chat_router


app = FastAPI(title="Skill Market API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(auth_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/categories")
def get_categories() -> dict:
    return {"items": list_categories()}


@app.get("/api/skills")
def get_skills(
    search: str = Query(default=""),
    tab: str = Query(default="all"),
    category: str = Query(default=""),
    user: dict | None = Depends(get_optional_user),
) -> dict:
    used_slugs: set[str] = set()
    if user is not None:
        used_slugs = manager.used_slugs(user["id"])
    return store_payload(search=search, tab=tab, category=category, used_slugs=used_slugs)


@app.get("/api/skills/{slug}")
def get_skill(slug: str) -> dict:
    skill = get_skill_by_slug(slug)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{slug}' not found")
    return skill.model_dump()
