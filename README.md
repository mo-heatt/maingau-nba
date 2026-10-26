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

## Tests

Engine logic and compliance rules are covered by pytest:

```sh
.venv/bin/python -m pytest backend/tests -q
```

- Unit tests (`test_clv`, `test_content`, `test_signals`, `test_scoring`, `test_arbitration`) run on handcrafted minimal inputs and need no mock data.
- `test_invariants` runs the engine on every customer of the real mock data and asserts zero violations: no sales during open complaints, dunning or cancellations, every chosen channel has consent, contact cap and minimum gain are respected, and the control group is deterministic at roughly 10%.

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

The rules baseline uses approved templates. The AI comparison path can generate personalised German drafts. Both can be downloaded as unsent `.eml` files with demo addresses. External email delivery is not connected.

## AI NBA comparison

Copy `.env.example` to `.env`, set the Hessian team `HAI_API_KEY`, and restart the backend. The key stays on the server and is excluded from Git. `NBA_AI_MODEL` defaults to `vllm/Kolibri-1`.

In **Customer 360**, select **Generate AI NBA**. The model assesses the full enabled catalogue from source facts, and the server checks evidence, policy and economics. A separate model request writes the German email draft for a valid actionable choice. Both are persisted. In **Marketing**, run a sample of 3 or 30 customers and inspect the saved results.

The original recommendation remains the comparison baseline. A full-catalogue AI comparison does not reuse the 16 legacy product relevance triggers. Generated AI offers are not approved for dispatch; source citations validate provenance, not the correctness of all model interpretations. Unknown prices and tariff eligibility require verification. Provider failures are shown explicitly. See [the AI contract](docs/ai-nba.md).

For repeatable adapter and failure tests, run the local Postman simulation:

```sh
postman simulation run postman/simulations/ai-nba.sim.yaml --port 4900
NBA_TEST_PROVIDER_URL=http://127.0.0.1:4900/hessian/v1 .venv/bin/python -m pytest backend/tests -q
```

This fixture is for automated tests only; the running application never substitutes it for real AI.

## Customer offer studio

Customer 360 includes observed usage/activity charts and a **Before / Now** switch. The AI view has email, call, web, push and SMS formats, a concrete demo tariff comparison, and an internal customer dossier. Generate each material separately; downloaded email drafts use the selected quote. The call format has discovery questions, a spoken offer, objection handling and contact-timing observations. Observed activity is not confirmed availability.

For a saved mobile example, open `http://127.0.0.1:5173/#customers?customer=MG-100005`. Demo offer interest is recorded locally and does not create a contract. All sending remains disabled. See the AI contract for price provenance and channel-preview limitations.

Email previews use the same escaped, branded HTML document as the HTML part of the downloaded `.eml`. The draft includes a plain-text alternative. AI generates copy; the server renders the MAINGAU layout and validated quote. The responsive email uses presentation tables and inline styles; browser preview and MIME structure are verified, but individual mail clients have not been exhaustively tested. `NBA_PUBLIC_APP_URL` sets the demo CTA destination (defaults to localhost).

Current Products & Providers shows the full known portfolio with category tabs and evidence. External contracts can be recorded from a stated source; competitor quotes are labelled separately. Forbidden channel generators are hidden and rejected by the API before inference. The Newsletter studio offers informational updates independently of an NBA, plus news-led commercial offers when all sales gates pass. Add official article sources with publication dates and reviewed facts; archived seed guides are clearly dated.
