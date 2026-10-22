"""Jev: the controller. Decides what the bot may read and whether an answer may be sent."""

import json
from pathlib import Path

import httpx

import settings
from prompts import JEV_PROMPT


def is_allowed(path: str | Path) -> bool:
    """True only for an existing doc file listed in, or inside a folder listed in, settings.json.
    resolve() follows symlinks and '..'."""
    p = Path(path).resolve()
    return (
        p.is_file()
        and p.suffix.lower() in settings.DOC_EXTENSIONS
        and (p in settings.ALLOWED_FILES or any(p.is_relative_to(root) for root in settings.ALLOWED_FOLDERS))
    )


def allowed_files() -> list[Path]:
    in_folders = (p for root in settings.ALLOWED_FOLDERS if root.is_dir() for p in root.rglob("*"))
    return sorted({p.resolve() for p in (*in_folders, *settings.ALLOWED_FILES) if is_allowed(p)})


def filter_chunks(chunks: list[dict]) -> list[dict]:
    """Drop retrieved chunks whose source is not (or no longer) allowed."""
    return [c for c in chunks if is_allowed(c["source"])]


def check_tone(answer: str) -> str | None:
    """Rule checks a small model can't do reliably. Returns the problem, or None."""
    low = answer.lower()
    if found := [w for w in settings.BLOCKED_WORDS if w in low]:
        return f"uses blocked words: {', '.join(found)}"
    if low.count("sorry") > 1:
        return "apologises more than once"
    if len(answer.split()) > settings.MAX_WORDS:
        return f"too long, keep it under {settings.MAX_WORDS} words"
    return None


async def check_answer(question: str, context: str, answer: str) -> tuple[bool, str]:
    """Rule checks first, then ask the Jev model one thing: is every fact in the context? Fails closed."""
    if problem := check_tone(answer):
        return False, problem
    prompt = JEV_PROMPT.format(context=context, answer=answer)
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={"model": settings.JEV_MODEL, "prompt": prompt, "format": "json", "stream": False, "options": {"temperature": 0}},
            )
            r.raise_for_status()
        verdict = json.loads(r.json()["response"])
        return verdict.get("supported") is True, str(verdict.get("why", ""))
    except (httpx.HTTPError, ValueError, KeyError, AttributeError) as e:
        return False, f"jev error: {e}"
