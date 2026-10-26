# AI NBA contract

The AI comparison path is separate from the existing rules baseline. It considers the full enabled catalogue; the 16 legacy relevance rules do not filter its choices. Deterministic consent, exclusions, contact caps and catalogue checks remain mandatory. Economics come from the existing scoring model using a neutral signal multiplier for every commercial product, not a model-generated probability.

GET `/api/ai/status`: provider readiness, model and sending-disabled flag.
GET `/api/customers/{id}/ai-context`: exact pseudonymised facts, permitted catalogue and policy sent to the model.
POST `/api/customers/{id}/ai-nba`: generate or reuse a saved result; `{ "refresh": true }` explicitly requests another generation.
GET `/api/customers/{id}/ai-nba`: latest saved result with current/stale status.
POST `/api/ai/batches`: start a persisted comparison job, `{ "limit": 30 }`, maximum 50. Only one active job per process, with at most three concurrent customer generations. Duplicate requests for one customer share a lock and reuse a current result. POST is idempotent while a job is running.
GET `/api/ai/batches/latest`: progress and per-customer results.

Each result stores the exact input hash, facts, policy/settings version, baseline comparison, model, prompt version, structured proposal, validations, usage and optional separately generated German email draft. Provider failures are recorded and surfaced; they never masquerade as AI decisions or replace the baseline. No external delivery occurs. Control-group members remain held out.

A valid evidence reference must exactly match a supplied fact quote or an unchanged, nonempty subset of its source fields. This establishes provenance, not semantic truth: free-text interpretation and email still require evaluation. Unknown availability, prices, savings or time series cannot be inferred from indicative catalogue prices or aggregate counters. All offers with unverified tariff eligibility are explicitly marked as requiring verification, not ready to send. Persisted results go stale when their input/settings change.

Provider defaults are configured in the root `.env` (a Developer area session key can override the key for one browser): `HAI_API_KEY`, `NBA_AI_BASE_URL`, `NBA_AI_MODEL`. The default Hessian model is `vllm/Kolibri-1`; its documented `/chat/completions` endpoint is used with JSON-schema response formatting and independent local validation. The gateway accepted this format in a live probe. `NBA_AI_JSON_SCHEMA=0` can disable the formatting request for a different provider. The app uses `python-dotenv` without overwriting process environment.

## Local evaluation, 26 October 2026

A stratified 30-customer run using Kolibri-1 and prompt v4 completed: 28 passed the implemented source/policy checks, 2 were blocked, and 11 unsent German drafts were saved. Among passing analyses, actions were 5 offers, 6 service contacts, 6 waits, 6 no-contact decisions and 5 human reviews. Four actionable choices/action types differed from the baseline (non-contact actions are compared without their baseline's informational product hint).

Blocked cases: one service suggestion had nonpositive estimated value; one non-contact decision incorrectly retained a product/channel. These were not converted into drafts. Manual inspection also found unsubstantiated qualitative savings language in some passing proposals: source-link validation does not prove a tariff is cheaper. This is a reason to retain comparison/review mode and complete pricing/eligibility data before autonomous dispatch. The mobile-data example selected Mobil Upgrade rather than the baseline internet cross-sell, citing the three-month usage counter and an actual support request.

`python scripts/evaluate_ai.py` regenerates the local evaluation JSON under ignored `data/evaluations/`. Do not interpret the pass rate as accuracy or measured uplift. The test suite passed 78 checks; AI provider success and failure paths were also exercised through the local Postman HTTP simulation.

## Concrete offers and channel materials

`GET /api/customers/{id}/insights` returns observed mobile aggregates, six months of dated activity and daily energy/charging readings. It does not invent monthly usage from a three-month counter. Behavioural series are suppressed without profiling consent.

`GET /api/customers/{id}/outreach-context` returns a concrete synthetic quote plus an internal dossier. Mobile variants are derived from the supplied tariff records: Mobil S 10 GB/9.99, Mobil M 30 GB/14.99, Mobil L 100 GB/24.99. The S-to-M comparison computes +20 GB and +5 EUR/month. These are demo reference prices, not verified current public offers. Other products use exact supplied prices or explicitly mark missing terms; internet speed/packages are not invented from a price range. Energy cost comparisons use the recorded annual consumption and tariff/base rates, not model arithmetic.

`POST /api/customers/{id}/outreach` takes `decision_id`, `channel`, and optional `refresh`. It generates a channel-specific material using the existing validated AI decision: a finished German email, an agent call kit, a web offer, push or SMS. Material and quote versions persist in SQLite. Material generation is coalesced per customer/channel. Only currently permitted channels can generate new materials. The server checks consent, channel availability, exclusions, economic threshold and holdout before calling the model, and rechecks after inference. The UI hides forbidden generators; saved historical drafts remain inspectable. `dispatch_allowed=false` still applies to every draft. Email materials also create a new downloadable unsent draft.

The call kit separates a third-person internal brief from a verbatim spoken opening, discovery questions, offer pitch, objections and closing. An internal dossier shows supplied contracts, signals, support/campaign history and permissions. Portal activity is displayed as observed two-hour windows in unspecified source time; confirmed free time remains unknown. It is never presented as a verified calling preference. Sensitive inferences such as pregnancy/health/family planning are prohibited, and private tracking details should not enter customer copy.

Validation checks source references, money versus GB units, computed quote amounts, unsupported savings language, contact-time claims, unverified dates, Du/Sie and channel lengths. Passing these checks does not prove every free-text interpretation. Contract availability, actual current commercial terms and eligibility still need verification before deployment.

`POST /api/customers/{id}/outreach/{materialId}/response` records a **demo** interested/not-now event in the audit trail. It never creates a contract and must not be counted as a real conversion for training or uplift estimates.

The customer page uses a Before/Now switch, a single channel workbench and concrete tariff card. Official MAINGAU images/links are presentation references, not a claim that the synthetic tariff can be purchased there. References: https://www.maingau-energie.de/mobilfunk, /strom, /gas, /internet, /smart-living, /onlineshop, /e-mobilitaet/autostrom and /service (checked 2026-10-26).


## Product portfolio and editorial newsletter

`GET /api/customers/{id}/products` exposes all known active contracts, connected devices, purchase records and explicitly stated competitor offers, each with a source reference and relationship type. A competitor quote is not treated as an active external contract. `POST /api/customers/{id}/external-products` records an explicitly reported external product and source evidence. These records and literal competing-offer evidence enter AI context and invalidate older decisions; no provider or tariff is guessed from absence of MAINGAU holdings.

`GET /api/customers/{id}/outreach-context` returns the allowed product-material generators and reasons. An independently permitted informational newsletter can be available even when the product decision cannot be used for newsletter sales. Both the toolbar and POST enforce the distinction.

The newsletter studio uses `GET /api/customers/{id}/newsletter-context`, `GET/POST /api/customers/{id}/newsletters`, and `POST /api/news`. Informational mode requires newsletter consent, DOI, an available channel, contact-cap room and no holdout; it does not require an actionable NBA or use behavioural targeting. Offer mode additionally requires a current validated commercial NBA and an eligible newsletter channel. News is a reason/context for a real catalogue offer, never permission to invent a discount.

Built-in editorial sources are archived official MAINGAU guides, with their original 2023/2024 publication dates shown. They are not described as current breaking news. Operators can supply a new official HTTPS source, publication date and editorial facts; these summaries are explicitly operator-supplied rather than automatically verified. No arbitrary URL is fetched server-side. Informational and offer newsletters get separate stored results, styled HTML previews and multipart email drafts. The selected source article and its publication date are part of the rendered email.

Channel availability is returned by `/api/customers/{id}/outreach-context` and shared by the offer toolbar and Customer 360 channel panel. `allowed_channels` means eligible for the current AI recommendation, including freshness, contact permission/availability, selected-product restrictions, per-channel value, and holdout checks. Each channel also exposes `contact_allowed`/`contact_reason`, so a consent grant is not confused with full offer eligibility. Generation checks the same policy again on the server. A helpful informational newsletter has its own purpose-specific gate (`editorial_newsletter`); it is not added to the personalised-offer toolbar merely because newsletter consent exists.

Outreach copy uses a bounded repair loop: one draft plus at most two content repairs. It stops at the first validated draft; provider failures stop immediately. Every repair keeps the selected NBA, channel, tone, quote and source facts, and the final result still rechecks decision freshness and channel eligibility. Saved materials include `attempts`, `max_attempts` and human-readable `failure_reasons`; blocked drafts are neither downloadable email drafts nor dispatchable. Du/Sie checks cover all advisor-spoken call fields; internal third-person briefs and customer-quoted objections do not impose the advisor's form of address. The UI offers explicit manual retry after the automatic limit, without regenerating the NBA.


Developer connection endpoints are GET/POST/DELETE `/api/developer/ai`. POST verifies the fixed configured gateway/model via `/models`, then stores the credential in server memory for up to 8 hours, referenced by an HttpOnly SameSite cookie. Credentials are not response fields, SQLite values or audit payloads; failed replacements preserve the old session. Request context and batch workers use that browser key before the server environment default. Developer-area validation errors deliberately omit submitted input values. This is not application authentication.

The customer list additionally returns an optional `preview` object with recorded products, profiling/language/tone context and service/contact counts. It does not return full service conversations or consent records for every row. The customer workspace separates the engine directory from a labelled saved AI overview and the material studio; the model decision and channel policy are shared by the detail components.
