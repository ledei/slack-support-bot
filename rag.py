import re

import chromadb
import httpx

import jev
import settings
from prompts import FALLBACK, SYSTEM_PROMPT

_collection = None


def collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        _collection = client.get_or_create_collection("docs", metadata={"hnsw:space": "cosine"})
    return _collection


def chunk(text: str, size: int = 800) -> list[str]:
    """Group paragraphs into chunks of about `size` characters."""
    chunks, current = [], ""
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        if current and len(current) + len(para) > size:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def ingest() -> int:
    """Rebuild the index from the allowed folders only, so deleted or moved docs disappear."""
    client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    try:
        client.delete_collection("docs")
    except Exception:  # first run: nothing to delete
        pass
    global _collection
    _collection = None
    col = collection()
    count = 0
    for path in jev.allowed_files():
        parts = chunk(path.read_text(encoding="utf-8", errors="ignore"))
        if parts:
            col.add(
                ids=[f"{path}#{i}" for i in range(len(parts))],
                documents=parts,
                metadatas=[{"source": str(path)} for _ in parts],
            )
            count += len(parts)
    return count


def near_best(hits: list[tuple], max_distance: float, margin: float) -> list:
    """hits = (item, distance), closest first. Keep items close enough overall AND close to the best match,
    so loosely related docs don't crowd in when the knowledge base is large."""
    if not hits or hits[0][1] > max_distance:
        return []
    return [item for item, dist in hits if dist <= max_distance and dist - hits[0][1] <= margin]


def retrieve(question: str) -> list[dict]:
    res = collection().query(query_texts=[question], n_results=settings.TOP_K)
    hits = [
        ({"text": doc, "source": meta["source"]}, dist)
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]
    return jev.filter_chunks(near_best(hits, settings.MAX_DISTANCE, settings.DISTANCE_MARGIN))


async def generate(question: str, context: str, feedback: tuple[str, str] | None = None, history: list | None = None) -> str:
    """feedback = (previous draft, why Jev blocked it), to ask for one rewrite.
    history = earlier (question, answer) pairs in the same Slack thread, oldest first."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for q, a in history or []:
        messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    messages.append({"role": "user", "content": f"Docs:\n{context}\n\nQuestion: {question}"})
    if feedback:
        # The checker says "CONTEXT"; the writer only knows "docs" and would echo the word.
        reason = re.sub(r"\bcontext\b", "docs", feedback[1], flags=re.I)
        messages += [
            {"role": "assistant", "content": feedback[0]},
            {"role": "user", "content": f"A checker rejected that answer: {reason}. Rewrite it so it fixes this and follows the rules. Reply with only the new answer."},
        ]
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={"model": settings.LLM_MODEL, "stream": False, "options": {"temperature": 0.2}, "messages": messages},
        )
        r.raise_for_status()
    return clean_draft(r.json()["message"]["content"])


def clean_draft(text: str) -> str:
    """Drop an "Answer:" label copied from the examples, or a "Sure, here's the revised answer:" opener."""
    opener = r"^\s*(?:answer:|(?:sure|okay|ok)?[,!.]?\s*here(?:'|’)?s (?:the|a|my) revised (?:answer|version)[^\n]*:)\s*"
    return re.sub(opener, "", text.strip(), flags=re.I).strip()


async def answer(question: str, history: list | None = None) -> dict:
    """history = earlier (question, answer) pairs in the same Slack thread, oldest first."""
    # A follow-up like "are you sure?" means nothing alone; search and judge it together with the earlier questions.
    topic = " ".join([q for q, _ in (history or [])[-2:]] + [question])
    chunks = retrieve(topic)
    if not chunks:
        return {"answer": FALLBACK, "sources": [], "jev": "no allowed docs matched"}
    context = "\n\n---\n\n".join(c["text"] for c in chunks)
    draft = await generate(question, context, history=history)
    ok, reason = await jev.check_answer(topic, context, draft)
    if not ok:  # one rewrite with Jev's reason; Jev checks it again
        draft = await generate(question, context, feedback=(draft, reason), history=history)
        ok, reason = await jev.check_answer(topic, context, draft)
    if not ok:
        return {"answer": FALLBACK, "sources": [], "jev": f"blocked: {reason}", "blocked_draft": draft}
    return {"answer": draft, "sources": sorted({c["source"] for c in chunks}), "jev": f"passed: {reason}"}


if __name__ == "__main__":
    print(f"Indexed {ingest()} chunks from {len(jev.allowed_files())} allowed files")
