import logging
import re
from collections import OrderedDict
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

import rag
import settings
from prompts import ERROR_REPLY

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")


def slack_escape(text: str) -> str:
    """Stop model output from becoming <!channel> pings, <@user> mentions or disguised <url|links>."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# shortcut: thread memory lives in this process, so a restart forgets it; use Slack's conversations.replies
# (needs the groups:history scope) if follow-ups across restarts matter.
THREADS: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()


def remember(thread: str, question: str, answer: str, max_threads: int = 500, max_turns: int = 4) -> None:
    """Keep the last few (question, answer) pairs per Slack thread, and only the most recent threads."""
    turns = THREADS.pop(thread, [])
    THREADS[thread] = (turns + [(question, answer)])[-max_turns:]
    while len(THREADS) > max_threads:
        THREADS.popitem(last=False)


def to_slack(text: str) -> str:
    """Escape, then turn Markdown **bold** into Slack's *bold*."""
    return re.sub(r"\*\*(.+?)\*\*", r"*\1*", slack_escape(text))


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not (settings.SLACK_BOT_TOKEN and settings.SLACK_APP_TOKEN):
        yield
        return
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_bolt.async_app import AsyncApp

    slack = AsyncApp(token=settings.SLACK_BOT_TOKEN)

    async def reply(event, say):
        thread = event.get("thread_ts") or event["ts"]
        question = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", "")).strip()
        if not question:
            await say(text="Hi! What can I help you with today?", thread_ts=thread)
            return
        key = f"{event.get('channel')}:{thread}"
        try:
            result = await rag.answer(question, history=THREADS.get(key, []))
            answer = result["answer"]
            remember(key, question, answer)
            # Status only: questions, and Jev's model-written reason, may hold personal details.
            log.info("slack %s answered: jev=%s sources=%s", event["type"], result["jev"].split(":", 1)[0],
                     [s.rsplit("/", 1)[-1] for s in result["sources"]])
        except Exception:  # e.g. Ollama down: never leave the person without a reply
            log.exception("answering failed")
            answer = ERROR_REPLY
        await say(text=to_slack(answer), thread_ts=thread)

    @slack.event("app_mention")
    async def on_mention(event, say):
        await reply(event, say)

    @slack.event("message")
    async def on_dm(event, say):
        # Only direct messages from people; channel messages need an @mention.
        if event.get("channel_type") == "im" and not event.get("bot_id") and not event.get("subtype"):
            await reply(event, say)
        else:
            log.info("slack message ignored: channel_type=%s subtype=%s bot=%s",
                     event.get("channel_type"), event.get("subtype"), bool(event.get("bot_id")))

    # Socket Mode: the bot connects out to Slack, so no public URL or open port is needed.
    handler = AsyncSocketModeHandler(slack, settings.SLACK_APP_TOKEN)
    await handler.connect_async()
    log.info("Connected to Slack (Socket Mode)")
    yield
    await handler.close_async()


api = FastAPI(title="Support bot", lifespan=lifespan)


class Ask(BaseModel):
    question: str


@api.get("/health")
def health():
    return {
        "ok": True,
        "slack": bool(settings.SLACK_BOT_TOKEN and settings.SLACK_APP_TOKEN),
        "allowed_folders": [str(d) for d in settings.ALLOWED_FOLDERS],
        "allowed_files": sorted(map(str, settings.ALLOWED_FILES)),
    }


# Local testing endpoint. shortcut: no auth, keep the server on localhost or remove before exposing it.
@api.post("/ask")
async def ask(body: Ask):
    return await rag.answer(body.question)
