"""Jev: the controller. Decides what the bot may read and whether an answer may be sent."""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import httpx
import numpy as np

import settings
from prompts import JEV_PROMPT, VERDICT_PROMPT


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
    # A `code` name (class, file, endpoint, command) must be in the docs: `InvoiceJob` once leaked in from a
    # prompt example. Compared without case, spacing or formatting.
    if invented := [c for c in re.findall(r"`([^`\n]+)`", answer) if _norm(c) not in _norm(context)]:
        return f"names code that is not in the docs: {', '.join(invented[:3])}"
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


def _similarities(question: str, texts: list[str]) -> list[float]:
    """Cosine similarity of the question to each text, with the embedding model search already uses (local, no LLM)."""
    global _embed
    if _embed is None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        _embed = DefaultEmbeddingFunction()
    q, *rest = (np.asarray(v) for v in _embed([question, *texts]))
    return [float(q @ t / (np.linalg.norm(q) * np.linalg.norm(t))) for t in rest]


def relevance(question: str, answer: str) -> float:
    return _similarities(question, [answer])[0]


def sentences(context: str) -> list[str]:
    """The context's sentences, without list markers or bold, so a quote of one reads as plain text."""
    lines = (re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).replace("**", "") for line in context.splitlines())
    return [s.strip() for line in lines for s in re.split(r"(?<=[.!?])\s+", line) if len(s.strip()) >= 25]


def repair_quotes(answer: str, context: str, min_ratio: float = 0.85) -> str:
    """The 3B writer often quotes a sentence almost word for word ("they scoring" for "its scoring"). Swap such a
    quote for the real sentence, or the real two sentences, so the reader sees the docs' words. Anything less
    close stays as it is and check_injection_and_facts still blocks it."""
    sents = sentences(context)
    candidates = sents + [f"{a} {b}" for a, b in zip(sents, sents[1:])]

    def fix(m: re.Match) -> str:
        quote = m.group(1)
        if quote_in_docs(quote, context):
            return m.group(0)
        q = _norm(quote)
        best = max(candidates, key=lambda c: SequenceMatcher(None, q, _norm(c), autojunk=False).ratio(), default=None)
        if best and SequenceMatcher(None, q, _norm(best), autojunk=False).ratio() >= min_ratio:
            return f'"{best}"'
        return m.group(0)

    return re.sub(r'"([^"\n]{25,})"', fix, answer)


async def deciding_sentence(question: str, context: str, top: int = 5) -> tuple[str, str] | None:
    """For a rewrite after a failed Yes/No check: the sentence in the context closest to the question that says
    yes or no on its own, and which. None when none of the closest few does."""
    sents = sentences(context)
    ranked = sorted(zip(_similarities(question, sents), sents), reverse=True)[:top] if sents else []
    for _, s in ranked:
        verdict = await _ask_json(settings.VERDICT_MODEL, VERDICT_PROMPT.format(question=_esc(question), quote=_esc(s)))
        if (v := str(verdict.get("verdict", "")).lower()) in ("yes", "no"):
            return s, v
    return None


# Escaped, so no spelling of a closing tag inside the text can end the data block.
_esc = lambda s: s.replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731


async def _ask_json(model: str, prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "format": "json", "stream": False, "options": {"temperature": 0, "seed": 0}},
        )
        r.raise_for_status()
    return json.loads(r.json()["response"])


async def check_verdict(question: str, answer: str) -> str | None:
    """A Yes/No answer must quote a sentence that itself says that Yes or No. Returns the problem, or None.
    check_injection_and_facts already made sure a word-for-word quote is there."""
    if not (m := re.match(r"\s*(yes|no)\b", answer, re.I)):
        return None
    said = m.group(1).lower()
    quotes = re.findall(r'"([^"\n]{25,})"', answer)
    for q in quotes:
        verdict = await _ask_json(settings.VERDICT_MODEL, VERDICT_PROMPT.format(question=_esc(question), quote=_esc(q)))
        if str(verdict.get("verdict", "")).lower() == said:
            return None
    return (f'the quoted sentence does not say "{said.capitalize()}"; quote the sentence that decides it, or say the '
            "docs don't say. If the question is not a yes/no question, do not start with Yes or No")


async def check_answer(question: str, context: str, answer: str) -> tuple[bool, str]:
    """Code checks first, then ask the Jev model one thing: is every fact in the context? Fails closed."""
    if problem := check_tone(answer) or check_injection_and_facts(context, answer):
        return False, problem
    # Grounded is not enough: "are you sure?" once got a well-sourced answer about unrelated PRs.
    if (score := relevance(question, answer)) < settings.MIN_RELEVANCE:
        return False, f"doesn't answer the question (relevance {score:.2f})"
    try:
        if problem := await check_verdict(question, answer):
            return False, problem
        verdict = await _ask_json(settings.JEV_MODEL, JEV_PROMPT.format(context=_esc(context), answer=_esc(answer)))
        claims = [c for c in verdict.get("claims", []) if isinstance(c, dict)]
        if unstated := [str(c.get("claim", "")) for c in claims if c.get("stated") is not True]:
            return False, f"not in the docs: {'; '.join(unstated[:2])}"
        return verdict.get("supported") is True, "every claim is in the docs"
    except (httpx.HTTPError, ValueError, KeyError, AttributeError) as e:
        return False, f"jev error: {e}"
