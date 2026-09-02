# Kilimo Hakika (DepotReady)

A deterministic **Pre-Travel Triage & Validation Engine** for Kenyan smallholder
farmers. It answers one question before a farmer spends scarce transport money
travelling to an NCPB depot: **will I actually be served?**

Three answers, every time:

1. **Will I be served?** — a binary `PROCEED` / `DO NOT TRAVEL` verdict.
2. **What am I lacking?** — an itemised list of the exact physical documents missing.
3. **What is the official cost?** — the statutory allocation and gazetted price.

Grounded in **MOALD Circular 2026/02** and **NCPB Operating Circular 4B**.

## Scope boundaries

Non-negotiable. No agronomic advice, no payments, no marketplace. See
`CLAUDE.md`.

## Running it

```bash
# 1. The verdict engine (FastAPI) — must be running for the frontend to work
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000        # Swagger UI at /docs

# 2. The web app (Next.js), in a second terminal
cp frontend/.env.example frontend/.env.local  # fill in the secrets
cd frontend && npm install && npm run dev     # http://localhost:3000
```

`frontend/.env.local` must set `KILIMO_TRIAGE_API_URL=http://127.0.0.1:8000`.
The frontend delegates every verdict to the FastAPI service and never computes
one locally.

## Layout

| Path | Purpose |
|---|---|
| `backend/` | The FastAPI verdict engine (`app/`, `main.py`) — the single source of truth for verdicts. Also `src/kilimo_hakika/`, the policy-pack/identity/assistant service. |
| `frontend/` | The Next.js app — farmer wizard and depot officer console |
| `database/` | Policy data, SQLite registry schema and seed |
| `docs/design/` | Design notes and the engine-consolidation record |

Full backend docs: `backend/README.md`. Project brief: `CLAUDE.md`.
