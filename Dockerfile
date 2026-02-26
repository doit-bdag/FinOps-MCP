FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src/ src/
COPY scripts/ scripts/

RUN uv pip install --system .

# Cloud Run injects identity via Workload Identity — no key files needed
ENV MCP_TRANSPORT=streamable-http
ENV PORT=8080

EXPOSE 8080

CMD ["python", "-m", "finops_mcp.server"]
