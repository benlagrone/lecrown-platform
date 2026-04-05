# Government Contracts

The platform can now pull Texas ESBD opportunities from `txsmartbuy.gov`, rank them against LeCrown-relevant work, and surface the strongest matches in the admin app.

## Source

- public ESBD page: `https://www.txsmartbuy.gov/esbd`
- ESBD service used by the site export: `https://www.txsmartbuy.gov/app/extensions/CPA/CPAMain/1.0.0/services/ESBD.Service.ss`

The backend uses the same `POST` flow the site uses for `Export to CSV`, bounded to a weekly window by default.

## Backend API

- `POST /contracts/refresh`
- `POST /contracts/{id}/funnel`
- `GET /contracts/list?limit=12&matches_only=true&open_only=true&min_priority_score=0`
- `GET /contracts/runs?limit=5`
- `GET /contracts/export.csv?window_days=7`
- `GET /contracts/keywords`
- `POST /contracts/keywords`
- `PATCH /contracts/keywords/{id}`
- `DELETE /contracts/keywords/{id}`
- `GET /contracts/agency-preferences`
- `POST /contracts/agency-preferences`
- `PATCH /contracts/agency-preferences/{id}`
- `DELETE /contracts/agency-preferences/{id}`

`POST /contracts/refresh` accepts:

```json
{
  "window_days": 7
}
```

Optional exact dates:

```json
{
  "start_date": "2026-03-27",
  "end_date": "2026-04-02"
}
```

Promote one matched contract into the CRM lead funnel:

```json
{
  "notes": "Priority target for business development",
  "force": false
}
```

That call creates a platform intake submission linked to the contract and then delivers the normalized lead payload to `EspoCRM`. The contract record stores:

- funnel status
- linked submission id
- downstream delivery status
- downstream CRM record id when available

## Weekly Run

From the repo root:

```bash
make gov-contracts-refresh
```

Direct command:

```bash
cd backend
python3 -m app.jobs.refresh_gov_contracts --window-days 7
```

Example cron entry for every Monday at 8:00 AM server local time:

```cron
0 8 * * 1 cd /Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/backend && /usr/bin/python3 -m app.jobs.refresh_gov_contracts --window-days 7
```

## Matching

The stored opportunity list stays complete. The admin UI filters what is shown in the view through:

- `Matched only`
- `Open only`
- `Min priority`

Keyword rules control fit matching and can be managed directly from the opportunities page. The default rules are tuned for LeCrown-style work, with heavier weight on:

- property management
- real estate
- building or facility maintenance
- construction, renovation, demolition, paving, concrete
- HVAC, electrical, plumbing, landscaping, janitorial

You can still extend the starting keyword set with `GOV_CONTRACT_EXTRA_KEYWORDS` in the environment, but the primary control surface is now the admin-managed keyword rule list.

## Score Matrix

Each stored opportunity now carries a score matrix:

- `Closeness`: normalized keyword-fit score
- `Timing`: due-date runway
- `Competition edge`: broad vs specialized bid heuristics
- `Agency affinity`: boost from preferred agencies
- `Priority`: weighted overall score used for sorting and the minimum-priority filter

Agency preferences are managed separately from keywords and let operators bias the ranked list toward target buyers without removing non-matching opportunities from storage.

## Funnel Behavior

Matches are not auto-sent to the CRM on refresh.

Current behavior:

- weekly refresh pulls and scores opportunities
- the admin UI shows ranked matches
- an operator can promote a contract into the lead funnel
- promotion creates an intake-style audit record and pushes the lead to `EspoCRM`

This keeps the contract source connected to the lead funnel without spamming the CRM with every weekly match.
