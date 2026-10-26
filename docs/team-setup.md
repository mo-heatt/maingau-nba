# Hessian AI for the team

The app already calls Hessian from FastAPI (`backend/app/ai_nba.py`), never from React. A Git checkout does not include the credential or local data. The integration branch combines `main` with the offer studio; source branches remain unchanged.

## Each developer runs locally

1. Install dependencies and add the supplied source dataset as described in README.
2. Copy `.env.example` to `.env` in the repository root (do not overwrite an existing configured file).
3. Set `HAI_API_KEY` to a valid credential issued for your team's access. Obtain it privately from the team/organisers; credentials are not in Git. Whether one event key can be distributed to every participant depends on its issued access terms; this project does not provision Hessian accounts or keys.

```dotenv
HAI_API_KEY=YOUR_ISSUED_KEY
NBA_AI_BASE_URL=https://hip-gw.hessian.ai/v1
NBA_AI_MODEL=vllm/Kolibri-1
NBA_AI_TIMEOUT_SECONDS=90
NBA_AI_JSON_SCHEMA=1
```

4. Restart the backend so it reads `.env`, then run the frontend normally.
5. Open `/api/ai/status`: `configured: true` means the key is present, not that Hessian has accepted it. Generate one NBA/material to verify connectivity and model access. HTTP 401/403 means check the issued credential/access; HTTP 429 means the provider is limiting traffic. Do not repeatedly retry configuration failures.

## One shared live app (recommended for using the demo together)

Run one FastAPI backend with the credential configured once on that server. Everyone uses its web address; users do not need the Hessian secret in their browsers or on their devices. All generations use that server's configured credential, so its available allowance/concurrency is shared.

Build the normal frontend with `npm run build --prefix frontend`, without `VITE_STATIC=1`. FastAPI serves that build together with `/api`, so the browser and API share one origin. The deployment start command is:

```sh
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Use a trusted team network or an authenticated HTTPS reverse proxy. This MVP has no application login: do not expose its write/generation endpoints to an unrestricted public audience. For a public deployment add team authentication, request/concurrency limits, secret configuration, and persistent storage for `data/nba.sqlite` and the source files. Set `NBA_PUBLIC_APP_URL` to the live app's public URL for email preview CTAs. A user's `127.0.0.1` always refers to their own machine.

## GitHub Pages is a separate snapshot demo

`VITE_STATIC=1` builds a read-only snapshot. It can show saved profiles and drafts; it cannot call Hessian, generate fresh text or persist server changes. Keep it as an offline pitch/demo. To enable live AI for the team, use the full backend option above; never put `HAI_API_KEY` in a `VITE_` variable, static snapshot or frontend bundle.
