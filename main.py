import logging
import re
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


MENTION = re.compile(r"<@[A-Z0-9]+>")


def from_slack(text: str) -> str:
    """Slack text back to plain text: drop mentions, undo the &lt; &gt; &amp; escaping."""
    text = MENTION.sub("", text)
    return text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").strip()


def thread_history(messages: list[dict], bot_user: str, current_ts: str, max_turns: int = 4) -> tuple[list, bool]:
    """From a Slack thread (oldest first), the (question, bot answer) pairs before current_ts, and whether
    the bot spoke last. Human chatter the bot never answered is left out."""
    earlier = [m for m in messages if m.get("ts") != current_ts and float(m.get("ts", 0)) < float(current_ts)]
    history, question = [], None
    for m in earlier:
        if m.get("user") == bot_user or m.get("bot_id"):
            if question is not None:
                history.append((question, from_slack(m.get("text", ""))))
                question = None
        else:
            question = from_slack(m.get("text", ""))
    bot_last = bool(earlier) and (earlier[-1].get("user") == bot_user or bool(earlier[-1].get("bot_id")))
    return history[-max_turns:], bot_last


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

    bot_user = (await slack.client.auth_test())["user_id"]

    async def read_thread(event) -> tuple[list, bool]:
        """The conversation so far, read from Slack each time, so it survives restarts."""
        if not event.get("thread_ts"):
            return [], False
        try:
            r = await slack.client.conversations_replies(channel=event["channel"], ts=event["thread_ts"], limit=50)
        except Exception as e:  # e.g. missing groups:history scope: answer without the thread
            log.warning("could not read thread: %s", getattr(e, "response", {}).get("error", type(e).__name__))
            return [], False
        return thread_history(r["messages"], bot_user, event["ts"])

    async def reply(event, say, history: list):
        thread = event.get("thread_ts") or event["ts"]
        question = from_slack(event.get("text", ""))
        if not question:
            await say(text="Hi! What can I help you with today?", thread_ts=thread)
            return
        try:
            result = await rag.answer(question, history=history)
            answer = result["answer"]
            # Status only: questions, and Jev's model-written reason, may hold personal details.
            log.info("slack %s answered: jev=%s sources=%s turns=%d", event["type"], result["jev"].split(":", 1)[0],
                     [s.rsplit("/", 1)[-1] for s in result["sources"]], len(history))
        except Exception:  # e.g. Ollama down: never leave the person without a reply
            log.exception("answering failed")
            answer = ERROR_REPLY
        await say(text=to_slack(answer), thread_ts=thread)

    @slack.event("app_mention")
    async def on_mention(event, say):
        history, _ = await read_thread(event)
        await reply(event, say, history)

    @slack.event("message")
    async def on_message(event, say):
        if event.get("bot_id") or event.get("subtype") or f"<@{bot_user}>" in event.get("text", ""):
            return  # bots, edits and joins; @mentions are handled by on_mention
        if event.get("channel_type") == "im":
            history, _ = await read_thread(event)
            await reply(event, say, history)
            return
        # In a channel, answer a follow-up without @mention only when the bot spoke last in that thread,
        # so it doesn't jump into every reply of a busy thread.
        history, bot_last = await read_thread(event)
        if bot_last:
            await reply(event, say, history)

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
