# Customer experience review and presentation flow

## Current friction

- `frontend/src/pages/Customer360.tsx`: a narrow 50-row picker competes with the customer detail; no explicit return to the directory.
- The recommendation follows the portfolio and charts. A jury must scroll before seeing the action and its explanation.
- Portfolio appears twice; the standalone newsletter and offer workbench can occupy the same long page.
- The directory preview exposes little beyond city, ID and company gain. No product, service or consent context is visible before opening a customer.
- Technical configuration belongs in a developer area, not the operator's main navigation.

## Design direction

Keep MAINGAU's Rondelle typography, navy (#002657) and yellow (#ffe500). Use the existing light surface (#ffffff / #f4f7fb) and dark surface (#121f31 / #0b1422) tokens. Reserve yellow for selected navigation and the primary next step. Use neutral ID-based avatars, never invented names or stock portraits presented as actual customers.

Directory: a full-width operational list with compact customer identity, business lines, the current engine action, permitted selected channel, risk and estimated gain. Search, filters, sorting and pagination are reflected in the URL. Show counts, clear empty states and a reset action. Keep the result list/filter position when returning from a profile.

Detail:
```
Customers / MG-100005                         Back to customers
Avatar · ID · city · tenure              language / Du–Sie
Customer value | churn estimate | products | open cases
Overview | Offer studio | Products | Insights | History | Permissions
Overview: proposed next step + reason | source observations
          contact/consent summary     | service alerts
```

The overview explicitly labels Engine vs a current validated AI decision. A source observation is not a claim about personal circumstances. Consent granted is not the same as an eligible personalised offer channel. Preserve this distinction in the presentation.

## Jury walkthrough (about one minute)

1. Show the directory: the whole customer base, visibly different needs and filterable cases.
2. Open the mobile example: current plan, observed usage and recommended next step, without scrolling through unrelated panels.
3. Open Offer studio: choose AI, inspect a concrete tariff and channel material; all sending remains disabled.
4. Open a service example: the service issue takes precedence; the Case Radar explains the alert.
5. Return to the directory with filters intact.

## Developer access

A labelled keyboard-accessible entry accompanies the logo's double-click shortcut. Hessian keys are held in server memory for a browser session, never in the frontend bundle, localStorage, Git or audit logs. Preserve the existing server .env configuration as the default. How it works is available in this developer area.


## Remaining product decisions

For a later iteration, separate service and marketing workspaces: service needs Case Radar and Customers, while marketing needs Recommendations, Customers and campaign settings. A workspace toggle is not access control; real permissions would need backend authentication. Keep the presentation honest about preview-only sending and conceptual learning feedback. The current list explicitly labels engine actions, while the detail can show a separately labelled saved AI proposal.

## Verification

The full backend suite passed with the local dataset and Postman provider simulation. Browser checks covered search, action filtering, pagination, deep-link reload, returning from a customer with the search intact, keyboard-operated light/system/dark controls, the double-click logo shortcut, developer tabs, and a malformed key that is rejected without an upstream request. The UI was inspected at desktop and 390px mobile width. No new live message sending or online model training was added.
