# Slack support bot

A local Slack support bot that answers only from your own help docs, in plain, polite language. Everything runs on your machine: Ollama for the models, Chroma for search, no cloud AI.

```
Slack ⇄ Socket Mode ─▶ Chroma (search docs) ─▶ Jev: drop anything not in settings.json
                                            ─▶ Qwen 2.5 3b writes the answer
                                            ─▶ Jev (Qwen 2.5 1.5B): backed by the docs and polite?
                                                 yes ─▶ reply in thread
                                                 no  ─▶ polite "a teammate will help"
```

## Adapt it to your product

Nothing in the code is product-specific. Change these:

| What | Where |
|---|---|
| What it knows | Your `.md`/`.txt` files in `knowledge/` (any folder depth), or other paths listed in `settings.json` |
| Which Slack workspace | `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` in `.env` (see Connect Slack) |
| Bot name | `slack-manifest.yaml` |
| Models | `LLM_MODEL` (writer) and `JEV_MODEL` (checker) in `.env` |
| Words it must never say | `BLOCKED_WORDS` in `.env`; add your internal terms |
| Tone and examples | `prompts.py` (examples use made-up articles on purpose) |

`knowledge/` ships with 6 demo articles, and `mock_private/` with fake secrets the bot must never reveal. Replace the demo articles with your own, and keep `mock_private/` for `check_bot.py`'s leak test. Anything you add to `knowledge/` is git-ignored, so your own docs stay local; only the demo files are in the repo.

## What Jev controls

| Check | Where | How |
|---|---|---|
| Only read allowed places | `jev.is_allowed` | real path (symlinks and `..` resolved) must be a file in `allowed_files` or inside an `allowed_folders` entry of `settings.json`, with an `allowed_extensions` type |
| Index holds nothing else | `rag.ingest` | rebuilds from `jev.allowed_files()` only |
| Search results are still allowed | `jev.filter_chunks` | rechecks every chunk's source on each question |
| Answer is safe to send | `jev.check_tone` + `jev.check_answer` | code blocks jargon, blame words, 2+ apologies, too long; then the judge model checks the advice is in the docs. Any error counts as FAIL. One rewrite allowed, then the polite fallback |

## The allowlist: settings.json

```json
{
  "allowed_folders": ["./knowledge"],
  "allowed_files": ["../handbook/faq.md"],
  "allowed_extensions": [".md", ".txt"]
}
```

A single file opens only that file, not its folder. If the file is missing or broken, or both lists are empty, the bot refuses to start. After any change, rebuild the index with `uv run python rag.py` (in Docker: `docker compose restart bot`).

## Run it

1. Edit `settings.json`: list the folders and single files the bot may read (paths relative to the file). Then `cp .env.example .env`.
2. `ollama pull qwen2.5:3b && ollama pull qwen2.5:1.5b` (writer and Jev).
3. `uv sync`
4. `uv run python rag.py` — builds the index. Rerun after docs change.
5. `uv run uvicorn main:api --port 8000`
6. Try it: `curl -X POST localhost:8000/ask -H 'content-type: application/json' -d '{"question":"I forgot my password"}'`

Tests: `uv run pytest`

## Check it on the mock data

`knowledge/` holds 6 fake help articles, some written technically on purpose. `mock_private/` holds fake secrets (salaries, an admin password, promo codes), each tagged `CANARY-…`, that the bot must never see. `knowledge/team-notes.md` is a symlink into it, and `knowledge/internal-script.py` is the wrong file type. Both are traps Jev must skip.

`uv run python check_bot.py` asks 9 questions the docs answer and 8 it must refuse (secrets, a prompt-injection attempt, general knowledge). It checks the index, every answer, every source, and that no secret appears. It exits 1 on any failure.

Results are not identical run to run, because the models aren't. Typical: 15–16 of 17 pass, and every miss so far was the polite fallback, never a leak.

`uv run python eval_ab.py [--jev] <models…>` compares writer and Jev models.

## Update the knowledge

1. Add, edit or delete `.md`/`.txt` files in `knowledge/`. Any folder depth works.
2. `./run.sh`

It checks Ollama and Docker are running, lists which docs are new, changed or removed since the last run, restarts the bot (rebuilding the index), and shows the indexed count and Slack status. A folder or file listed in `settings.json` that doesn't exist stops startup with its name.

## Run it in Docker

Ollama stays on the host by default (a Mac's GPU isn't reachable from Docker). Pull the models there first.

1. `docker compose up -d --build`. `settings.json` and `./knowledge` are mounted read-only, and the index is rebuilt on every start. If `settings.json` lists other paths, add a matching `:ro` mount for each in `compose.yaml`.
2. Try it: same `curl` as above, on `localhost:8000`.
3. Docs changed? `docker compose restart bot`

On a server without Ollama: `DOCKER_OLLAMA_URL=http://ollama:11434 docker compose --profile ollama up -d`, then `docker compose exec ollama ollama pull qwen2.5:3b` and the same for `qwen2.5:1.5b`.

## Connect Slack

Uses Socket Mode: the bot connects out to Slack, so no public URL, ngrok or open port is needed.

1. https://api.slack.com/apps → **Create New App** → **From a manifest** → pick your workspace → paste `slack-manifest.yaml` → **Create**.
2. **Basic Information** → **App-Level Tokens** → **Generate Token and Scopes** → add scope `connections:write` → copy the `xapp-…` token to `SLACK_APP_TOKEN` in `.env`.
3. **Install App** → **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-…`) to `SLACK_BOT_TOKEN` in `.env`.
4. Restart the bot (`docker compose up -d` or uvicorn). `/health` shows `"slack": true` and the log says `Connected to Slack (Socket Mode)`.
5. In Slack: DM **Support Bot**, or `/invite @Support Bot` to a channel and @mention it. It replies in a thread.

**Thread chat.** The bot reads the whole Slack thread each time, so follow-ups keep the conversation, also after a restart. In a channel it answers a follow-up without an @mention only when it was the last to speak in that thread; otherwise mention it. This needs the `channels:history` and `groups:history` scopes and the `message.channels` and `message.groups` events from `slack-manifest.yaml`. If you created the app from an older manifest: **App Manifest** → paste the new one → **Save**, then **Install App** → **Reinstall to Workspace**.

## Tone

The writing rules live in `prompts.py`. They come from `docs/research/plain-language-support.md`.
