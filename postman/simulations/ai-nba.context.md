# AI NBA simulation

Local provider contract fixture, created 2026-10-26. A Postman workspace search for Hessian AI returned no owner workspace; the mock implements the documented chat-completions request shape from the event access sheet and the envelope observed from the live gateway.

## Purpose

Exercise the actual HTTP adapter, JSON validation, policy checks, persistence and failure handling without consuming the team model quota. This is never a runtime fallback.

## Execution

Start `postman simulation run postman/simulations/ai-nba.sim.yaml --port 4900 --output ndjson`. Run `NBA_TEST_PROVIDER_URL=http://127.0.0.1:4900/hessian/v1 .venv/bin/python -m pytest backend/tests -q`. Stop the simulation with Ctrl-C.

## Assumptions

- The fixture models the gateway's chat-completions envelope, not language quality, inference latency or all model capabilities. Passing it cannot establish recommendation usefulness. (Observed 2026-10-26, live gateway and `test_ai_nba.py`.)
- Full-context integration tests require the local dataset; they use a copied temporary SQLite database and a fixture API key, never the production credential. (Observed 2026-10-26.)

## Observations

<!-- begin:observations -->
2026-10-26: 96 tests passed, including AI, chart-data and channel-material checks. The sole member `hessian-chat` received chat-completions requests for successful NBA/email generation, invalid product, fabricated evidence, malformed JSON, HTTP 503 and timeout. No members were silent. Consent/DOI denial, product portfolio provenance and independent informational/news-led offer newsletters were also exercised. The same member also served concrete-quote email/call/SMS material generation and fabricated-price rejection. An independent live Kolibri comparison of 30 customers completed with 28 source/policy passes, 2 blocked decisions and 11 drafts; it does not establish commercial accuracy.
<!-- end:observations -->

## What didn't work

- 2026-10-26: the manifest initially failed with `Manifest version must be 1`; the committed manifest includes `version: 1` and scenario `path`.
