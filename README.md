# MAINGAU Next Best Action engine

Futury Build Days #3 (26–27 Oct 2026), MAINGAU Energie challenge "One customer, every channel".

For each customer, the engine picks the one action with the highest expected gain in customer lifetime value (CLV): an offer, a proactive service fix, or no contact. It also picks the channel the customer agreed to and the tone (Du/Sie) they write in. Consent and exclusions are applied before ranking, so the engine never sells to someone with an open complaint, dunning or a cancellation.

## Run it

The mock data is not in this repository. Put `maingau_nba_mockdata.xlsx` and `event_stream_2026-10-01.jsonl` in `data/`, then:

    pip install pandas openpyxl
    python export.py      # engine + event replay + legacy audit -> out/engine_output.json
    python build_web.py   # web app -> out/nba_console.html (open in a browser)

`export.py` prints a self-check; it must report 0 consent or exclusion violations.

## Scoring

From the `clv_method` sheet:

    dCLV = p(accept) × (CLV after accept − CLV now) + (1 − p) × (CLV after reject − CLV now) − contact cost

- CLV: 10 years at 6%, from `customer_value` and `value_assumptions`.
- p(accept): conversion rate per offer × channel × tone in `nba_action_history`, smoothed toward the offer and global rate.
- A sales contact during an open complaint or dunning raises churn, so it scores negative.

## Files

| File | What it does |
|---|---|
| `engine.py` | Customer state, candidate offers, rules, dCLV scoring, arbitration, message |
| `export.py` | Event replay, legacy audit, self-check, JSON export |
| `templates.py` | Approved German message templates, Du and Sie |
| `app.html` | Web app template: Recommendations, Marketing, Customer 360°, How it works |
| `build_web.py` | Puts the engine output into `app.html` → `out/nba_console.html` |
| `build_360.py` | Joins all source sheets and the event stream into one profile and timeline per customer, for the 360 new tab |
| `nba/`, `run.py` | Second, independent engine used as a cross-check (`python run.py`) |

Tunable assumptions are at the top of `engine.py` (`SETTINGS`, `SIGNAL_LIFT`, `INTENT_LIFT`).

## Web app

- **Recommendations:** one next best action per customer, with the one-line reason and a downloadable decision log.
- **Marketing:** contact limit, minimum gain, tone, offers and priorities, channels; approval queue; text approval.
- **Customer 360°:** status, CLV, every option scored, change a decision, AI personalisation inside the approved template.
- **360 new:** every source system joined around one customer: what they hold in each business line and the best next product where they hold nothing, channels and permissions, one timeline across service, campaigns, newsletter, portal, shop, charging, smart home, consent and live events, plus value, home energy, charging and service panels, and which of the 18 sources hold data on them.
- **How it works:** Decide / Explain / Learn, the 7-step pipeline, live events, control group and uplift, target architecture on Databricks with MCP.

When published as a claude.ai artifact, approvals and settings are shared with the team and the AI writing uses the viewer's Claude account. Opened as a plain file, the app saves them in the browser only.
