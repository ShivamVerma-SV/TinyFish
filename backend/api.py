"""HTTP boundary for the RoleCurrent frontend."""

from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from .job_service import TinyFishError, discover_jobs


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

app = FastAPI(title="RoleCurrent API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class SearchPreferences(BaseModel):
    role: str = Field(min_length=2, max_length=120)
    location: str = Field(default="", max_length=160)
    locationScope: Literal["preferred", "remote", "anywhere"] = "preferred"
    skills: list[str] = Field(default_factory=list, max_length=12)
    opportunityType: Literal["Internship", "Full-time", "Both"] = "Both"
    experienceLevel: Literal["Entry-level", "Mid-level", "Senior", "Any"] = "Any"
    useAgent: bool = False
    maxResults: int = Field(default=16, ge=1, le=30)

    @field_validator("role", "location")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            skill = " ".join(value.split())[:40]
            if skill and skill.lower() not in {item.lower() for item in cleaned}:
                cleaned.append(skill)
        return cleaned[:12]

    @model_validator(mode="after")
    def require_preferred_location(self) -> "SearchPreferences":
        if self.locationScope == "preferred" and not self.location:
            raise ValueError("A location is required when using preferred-location search.")
        return self


@app.get("/api/status")
def status() -> dict[str, object]:
    return {
        "name": "RoleCurrent",
        "keyConfigured": bool(os.getenv("TINYFISH_API_KEY", "").strip()),
        "capabilities": {"search": True, "fetch": True, "agent": True},
    }


@app.post("/api/search")
def search(preferences: SearchPreferences) -> StreamingResponse:
    events: queue.Queue[dict[str, object] | None] = queue.Queue()

    def publish(event: dict[str, object]) -> None:
        events.put(event)

    def worker() -> None:
        try:
            result = discover_jobs(preferences.model_dump(), publish)
            publish({"type": "complete", "result": result})
        except TinyFishError as exc:
            publish(
                {
                    "type": "error",
                    "error": {
                        "code": "MISSING_API_KEY" if exc.service == "Configuration" else "DISCOVERY_FAILED",
                        "message": str(exc),
                    },
                }
            )
        except Exception:
            publish(
                {
                    "type": "error",
                    "error": {
                        "code": "REQUEST_FAILED",
                        "message": "The search could not be completed. Please retry; no credentials or private details were logged.",
                    },
                }
            )
        finally:
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            event = events.get()
            if event is None:
                break
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache"})


frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
