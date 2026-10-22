import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def load_allowlist(path: Path) -> tuple[list[Path], set[Path], set[str]]:
    """Read settings.json. Relative paths are relative to the file. A missing or broken file stops startup."""
    data = json.loads(path.read_text())

    def resolve(p: str) -> Path:
        return (path.parent / Path(p).expanduser()).resolve()

    folders = [resolve(p) for p in data.get("allowed_folders", [])]
    files = {resolve(p) for p in data.get("allowed_files", [])}
    extensions = {e.lower() for e in data["allowed_extensions"]}
    if not folders and not files:
        raise ValueError(f"{path}: allowed_folders and allowed_files are both empty")
    # A typo or a missing Docker mount would otherwise drop docs silently.
    if missing := [str(p) for p in folders if not p.is_dir()] + [str(p) for p in files if not p.is_file()]:
        raise ValueError(f"{path}: these allowed paths don't exist: {', '.join(missing)}")
    return folders, files, extensions


# The only places the bot may read. Jev enforces this.
ALLOWED_FOLDERS, ALLOWED_FILES, DOC_EXTENSIONS = load_allowlist(Path(__file__).parent / "settings.json")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")
JEV_MODEL = os.getenv("JEV_MODEL", "qwen2.5:1.5b")

# Jev blocks answers containing any of these (case-insensitive). Engineering readers, so technical words are fine;
# these catch blame and the writer leaking prompt words.
BLOCKED_WORDS = [w.strip().lower() for w in os.getenv(
    "BLOCKED_WORDS", "obviously,your fault,revised answer,revised version,the context",
).split(",") if w.strip()]
MAX_WORDS = int(os.getenv("MAX_WORDS", "200"))
# Minimum question-answer similarity (same embedding model as search). Slack test: good 0.34-0.77, off-topic <= 0.24.
MIN_RELEVANCE = float(os.getenv("MIN_RELEVANCE", "0.3"))

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma")
TOP_K = int(os.getenv("TOP_K", "4"))
# Chroma cosine distance (all-MiniLM). With 91 docs: right doc 0.32-0.71, "CEO salary" 0.77.
MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.75"))
# Also drop chunks more than this behind the best match (loosely related docs were +0.22 to +0.50).
DISTANCE_MARGIN = float(os.getenv("DISTANCE_MARGIN", "0.12"))

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")  # xapp-..., for Socket Mode
