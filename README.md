# MAINGAU Next Best Action

Futury Build Days #3, MAINGAU Energie challenge: “One customer, every channel”.

React workspace backed by a FastAPI API and SQLite. A single Python engine builds Customer 360 profiles, applies consent and exclusions, scores candidates by expected customer lifetime value gain, and chooses an action, channel and German Du/Sie message.

## Run locally

Use Python 3.9+ and Node.js 22.12+. The event data is intentionally excluded from Git. Place `maingau_nba_mockdata.xlsx` and `event_stream_2026-10-01.jsonl` in `data/`.

Install dependencies from the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm ci --prefix frontend
```

Start the backend:

```sh
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

In another terminal, start the frontend:

```sh
npm run dev --prefix frontend
```

Open http://127.0.0.1:5173/. The development server proxies `/api` to port 8001. API documentation is at http://127.0.0.1:8001/api/docs.

The backend imports the workbook on first startup into `data/nba.sqlite`. Settings, reviews, overrides, drafts and audit records persist there. Set `NBA_DB_PATH` to use a different database file.

Build the frontend with `npm run build --prefix frontend`. Starting the backend after that build also serves the compiled frontend at port 8001.

## Structure

- `frontend/src/`: React and TypeScript pages for Recommendations, Marketing, Customer 360 and How it works.
- `backend/app/engine/`: customer state, signals, scoring, arbitration, event application and approved German templates.
- `backend/app/service.py`: shared decision service, settings, reviews and overrides.
- `backend/app/database.py`, `ingestion.py`: SQLite persistence and source import.
- `backend/app/main.py`: HTTP API and optional compiled frontend hosting.
- `backend/app/replay.py`: event replay preview, ordered by arrival time and deduplicated by event ID.
- `legacy/`: original static console and both historical engine implementations, retained for reference. The new application does not import these files.

## Behavior and limits

Consent, profiling, complaints, dunning, cancellation, contact limits, allowed channels and text approvals constrain recommendations. Reviews refer to a specific decision version; changed decisions require a new review. Stable control assignments hold customers out of the approval queue.

Expected gain uses the workbook's CLV assumptions and historical acceptance estimates. These are model estimates on synthetic event data, not guaranteed outcomes. Event replay is a dry run and reports unsupported event types; it does not persist live customer updates.

Messages currently use approved templates. Drafts can be stored and downloaded as unsent `.eml` files with demo addresses. External email delivery and live AI personalisation are not connected.
