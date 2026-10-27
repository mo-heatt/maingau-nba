# Example files for the customer import

Use these with **Import customer** on the Customers page. Each file holds exactly one customer. The dialog only checks a file until you click **Create customer**; created customers cannot be deleted, so try them on a copy of `data/nba.sqlite` first (`NBA_DB_PATH`).

| File | What it tests |
| --- | --- |
| `neukunde-offenbach.csv` | German Excel style: `;` separator, `ja`/`nein`, SMS consent withdrawn, empty `customer_id` (the next free ID is assigned). |
| `neukunde-darmstadt.json` | JSON with nested `customer` and `consents`; newsletter consent with a double opt-in date, so the newsletter channel can open. |
| `new-customer-frankfurt-en.csv` | Minimal file: `,` separator, English, only two consents. Shows the warnings: missing consents become `not_given`; newsletter without double opt-in stays blocked. |
| `fehlerhaft.csv` | Deliberately broken: existing ID, no city, household 0, language `fr`, too young, date in the future, invalid yes/no and consent values. All problems are listed at once; nothing is stored. |

New customers have no contracts yet, so the engine usually recommends **No action** and CLV starts at 0 €.
