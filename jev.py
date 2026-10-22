"""Jev: the controller. Decides what the bot may read and whether an answer may be sent."""

import json
import re
from pathlib import Path

import httpx
import numpy as np

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


# Any scheme://… (fails closed: IPs, localhost, any host) or a bare domain, non-Latin included.
LINK = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s)>\]]+|(?:www\.)[^\s)>\]]+|(?:[\w-]+\.)+[^\W\d_]{2,}(?:/[^\s)>\]]*)?", re.I)
PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
# Tags and "supported:" in any case or spacing; the uppercase labels only, so "your answer" stays fine.
STEERING = re.compile(r"[{}]|(?i:<\s*/?\s*(?:context|answer)\b)|\bCONTEXT\b|\bANSWER\b|(?i:\"?supported\"?\s*:)")


def links(text: str) -> set[str]:
    return {re.sub(r"^(?:[a-z][a-z0-9+.-]*://)?(?:www\.)?", "", m.lower()).rstrip("/.,") for m in LINK.findall(text)}


def phones(text: str) -> set[str]:
    return {re.sub(r"\D", "", m) for m in PHONE.findall(text)}


def _norm(s: str) -> str:
    """Ignore formatting, spacing, case and apostrophe style; nothing else."""
    s = re.sub(r"[’‘ʼ´]", "'", re.sub(r"[`*_]", "", s))
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_in_docs(quote: str, context: str) -> bool:
    """A quote must be word for word from the docs. Allowing paraphrases was tried and removed: every rule
    for "close enough" (word overlap, negation pairs, qualifier lists) had a way to change the meaning."""
    q = _norm(quote).rstrip(".")
    return bool(re.search(r"[a-z0-9]", q)) and q in _norm(context)


def check_injection_and_facts(context: str, answer: str) -> str | None:
    """Checks a prompt can't talk its way past. Returns the problem, or None."""
    # JSON, our tags or the checker's labels in a draft can only be an attempt to steer the checker.
    # Braces are normal inside code (`/api/goal/{goalId}`), so only text outside backticks counts for them.
    prose = re.sub(r"```.*?```|`[^`\n]*`", "", answer, flags=re.S)
    if re.search(r"[{}]", prose) or STEERING.search(answer.replace("{", "").replace("}", "")):
        return "looks like it is trying to steer the checker"
    # A bold name right after "go to", "tap", "click"… is a menu or button; it must exist in the docs
    # (no invented "Settings"). Bold used for emphasis or headings is fine.
    nav = r"(?:go to|open|tap|click|select|choose|press)\s+(?:on\s+|the\s+)?\*\*(.+?)\*\*"
    labels = (p.strip() for b in re.findall(nav, answer, flags=re.I) for p in re.split(r"\s*(?:>|→|,|/)\s*", b))
    if invented := [p for p in labels if p and p.lower() not in context.lower()]:
        return f"names menus or buttons not in the docs: {', '.join(invented)}"
    # A "quoted" sentence presents itself as the docs' own words, so it must really come from the docs.
    if fake := [q for q in re.findall(r'"([^"\n]{25,})"', answer) if not quote_in_docs(q, context)]:
        return f"quotes text that is not in the docs: {fake[0][:60]}"
    # A yes/no verdict is where the writer's own assumptions slip in, so it must rest on a quote from the docs.
    if re.match(r"\s*(yes|no)\b", answer, re.I) and not re.search(r'"[^"\n]{25,}"', answer):
        return "a yes/no answer must quote the sentence from the docs that decides it"
    # Exact match, not substring: help.example.co must not pass because help.example.com is in the docs.
    if made_up := sorted((links(answer) - links(context)) | (phones(answer) - phones(context))):
        return f"link or number not in the docs: {', '.join(made_up)}"
    return None


_embed = None


def relevance(question: str, answer: str) -> float:
    """Cosine similarity of question and answer, with the embedding model search already uses (local, no LLM)."""
    global _embed
    if _embed is None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        _embed = DefaultEmbeddingFunction()
    q, a = (np.asarray(v) for v in _embed([question, answer]))
    return float(q @ a / (np.linalg.norm(q) * np.linalg.norm(a)))


async def check_answer(question: str, context: str, answer: str) -> tuple[bool, str]:
    """Code checks first, then ask the Jev model one thing: is every fact in the context? Fails closed."""
    if problem := check_tone(answer) or check_injection_and_facts(context, answer):
        return False, problem
    # Grounded is not enough: "are you sure?" once got a well-sourced answer about unrelated PRs.
    if (score := relevance(question, answer)) < settings.MIN_RELEVANCE:
        return False, f"doesn't answer the question (relevance {score:.2f})"
    # Escaped, so no spelling of a closing tag inside the text can end the data block.
    esc = lambda s: s.replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    prompt = JEV_PROMPT.format(context=esc(context), answer=esc(answer))
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
