FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# Bake Chroma's embedding model into the image so startup needs no download.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as E; E()(['warm up'])"

COPY *.py ./

# Rebuild the index from the mounted docs on every start, so it always matches them.
CMD ["sh", "-c", "python rag.py && uvicorn main:api --host 0.0.0.0 --port 8000"]
