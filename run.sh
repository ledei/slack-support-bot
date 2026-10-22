#!/usr/bin/env bash
# Start or restart the bot with the latest knowledge. Run: ./run.sh
# Shows which docs are new, changed or removed since the last run, then rebuilds the index.
set -euo pipefail
cd "$(dirname "$0")"

curl -sf -m 3 http://localhost:11434/api/version >/dev/null \
  || { echo "Ollama isn't running. Open the Ollama app, then run ./run.sh again."; exit 1; }
docker info >/dev/null 2>&1 \
  || { echo "Docker isn't running. Open Docker Desktop, then run ./run.sh again."; exit 1; }

# Compare the allowed docs with the last run. Also fails here if settings.json is broken.
uv run --quiet python - <<'EOF'
import json
from pathlib import Path

import jev

snapshot = Path(".knowledge-snapshot.json")
old = json.loads(snapshot.read_text()) if snapshot.exists() else {}
now = {str(p): p.stat().st_mtime_ns for p in jev.allowed_files()}
cwd = str(Path.cwd()) + "/"
short = lambda paths: ", ".join(sorted(p.removeprefix(cwd) for p in paths)) or "none"

print(f"Knowledge: {len(now)} files")
print(f"  new:     {short(now.keys() - old.keys())}")
print(f"  changed: {short(p for p in now.keys() & old.keys() if now[p] != old[p])}")
print(f"  removed: {short(old.keys() - now.keys())}")
Path(".knowledge-snapshot.next.json").write_text(json.dumps(now, indent=1))
EOF

# --force-recreate: the index is rebuilt on every start, so this always picks up the docs.
docker compose up -d --build --force-recreate bot >/dev/null 2>&1

for _ in $(seq 1 90); do
  health=$(curl -sf -m 2 http://localhost:8000/health) && break
  sleep 1
done
if [ -z "${health:-}" ]; then
  echo "The bot didn't start. Last log lines:"
  docker compose logs --tail 20 bot
  exit 1
fi

mv .knowledge-snapshot.next.json .knowledge-snapshot.json  # only after a good start
docker compose logs bot | grep -E "Indexed|Connected to Slack" | sed 's/^bot-1  | //'
echo "$health" | grep -q '"slack":true' || echo "Slack: not connected (tokens missing in .env?)"
echo "Ready. Test page: http://localhost:8000/docs"
