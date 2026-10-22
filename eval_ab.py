"""A/B the writer and Jev models. Run: uv run python eval_ab.py [--jev] qwen2.5:1.5b qwen2.5:3b"""

import asyncio
import re
import sys
import time

import jev
import rag
import settings

QUESTIONS = [
    "I forgot my password, what do I do?",
    "my company uses SSO and I can't log in",
    "my steps stopped updating since yesterday",
    "the reset link says it expired",
    "I haven't opened the app in months and now my watch won't sync",
]
JARGON = ["token", "oauth", "backfill", "webhook", "401", "re-authori", "integration", "[provider]"]

# Labelled answers for testing Jev: (question, answer, should_pass)
JEV_CASES = [
    ("I forgot my password, what do I do?", "Thanks for asking! 1. Open the login page and click **Forgot password**. 2. Enter your email. We'll send a link within 5 minutes. If it doesn't arrive, check your spam folder or reply here.", True),
    ("I forgot my password, what do I do?", "Thanks! Call our support line at 0800-123-456 and we'll reset it over the phone within 2 minutes.", False),
    ("I forgot my password, what do I do?", "You typed the wrong password, obviously. Click Forgot password and be more careful next time.", False),
    ("my steps stopped updating since yesterday", "Thanks for letting us know! Your watch lost its connection to the app. 1. Go to **Settings → Connected apps**. 2. Tap your watch, then **Reconnect**. Your last 7 days should show up within about 15 minutes. If not, reply here.", True),
    ("my steps stopped updating since yesterday", "The provider webhook returned HTTP 401 because the OAuth refresh token was revoked. Re-authorise the integration so the backfill job can run.", False),
    ("my steps stopped updating since yesterday", "Thanks! Just delete the app and reinstall it, then your steps will come back instantly.", False),
    # Real qwen2.5:3b drafts from earlier runs.
    ("I forgot my password, what do I do?", '1. Open the login page.\n2. Click "Forgot password".\n3. Enter your email.\n4. Check your email within 5 minutes for a reset link.\n5. Use the link within 1 hour.\n6. If not received, try again or ask IT.\nIf still stuck, reply here and a teammate will help.', True),
    ("the reset link says it expired", 'Thanks! The reset link expires after 1 hour. Click "Forgot password" again to get a new one. If it still doesn\'t work, reply here and a teammate will help.', True),
    ("my company uses SSO and I can't log in", 'Thanks! For SSO, you need to ask your company\'s IT team to reset your password. They can use the "Forgot password" option provided by your company\'s SSO system. They\'ll send you a reset link via email. If you need more help, let me know!', False),
    ("my steps stopped updating since yesterday", "1. Go to **Settings > Connected apps**.\n2. Find and click on the provider causing issues.\n3. Click **Reconnect**.\n4. Wait for backfill to complete (usually 15 mins).\nIf not updated, reply here and a teammate will help.", False),
    ("I haven't opened the app in months and now my watch won't sync", "1. Go to **Settings**.\n2. Tap **Connected apps**.\n3. Find the provider (like Fitbit, Apple Watch, etc.).\n4. Tap **Reconnect**.\n5. A backfill job will sync your last 7 days of activity.\nIt might take 15 minutes. If still not working, ask for help here.", False),
]


def score(answer: str) -> dict:
    low = answer.lower()
    return {
        "words": len(answer.split()),
        "steps": bool(re.search(r"^\s*1[.)]", answer, re.M)),
        "jargon": [j for j in JARGON if j in low],
        "sorry": low.count("sorry"),
    }


async def main(models: list[str]):
    rag.ingest()
    print("## Writers (Jev off)\n")
    for model in models if not JEV_ONLY else []:
        settings.LLM_MODEL = model
        for q in QUESTIONS:
            chunks = rag.retrieve(q)
            context = "\n\n---\n\n".join(c["text"] for c in chunks)
            t = time.perf_counter()
            draft = await rag.generate(q, context) if chunks else "(no docs matched)"
            print(f"### {model} | {q}  ({time.perf_counter() - t:.1f}s)\n{score(draft)}\n{draft}\n")

    print("## Jev accuracy on labelled answers\n")
    for model in models:
        settings.JEV_MODEL = model
        right, t = 0, time.perf_counter()
        for q, a, want in JEV_CASES:
            context = "\n\n---\n\n".join(c["text"] for c in rag.retrieve(q))
            ok, reason = await jev.check_answer(q, context, a)
            right += ok == want
            mark = "ok " if ok == want else "XX "
            print(f"{mark}{model} | want={'PASS' if want else 'FAIL'} got={'PASS' if ok else 'FAIL'} | {q[:30]} | {reason}")
        print(f"**{model}: {right}/{len(JEV_CASES)} correct, {time.perf_counter() - t:.1f}s total**\n")


JEV_ONLY = "--jev" in sys.argv

if __name__ == "__main__":
    asyncio.run(main([a for a in sys.argv[1:] if a != "--jev"] or ["qwen2.5:1.5b", "qwen2.5:3b"]))
