# Government Contracts

The platform can now pull Texas ESBD opportunities from `txsmartbuy.gov`, federal forecast opportunities from `acquisitiongateway.gov`, grant opportunities from `simpler.grants.gov`, SBA SUBNet subcontracting opportunities from `sba.gov`, and a first wave of municipal/county/regional Texas procurement sources, rank them against LeCrown-relevant work, and surface the strongest matches in the admin app.

## Source

- public ESBD page: `https://www.txsmartbuy.gov/esbd`
- ESBD service used by the site export: `https://www.txsmartbuy.gov/app/extensions/CPA/CPAMain/1.0.0/services/ESBD.Service.ss`
- public federal forecast page: `https://acquisitiongateway.gov/forecast`
- federal forecast JSON feed used by the site listing and CSV export batching: `https://ag-dashboard.acquisitiongateway.gov/api/v3.0/resources/forecast?_format=json`
- public grants search page: `https://simpler.grants.gov/search`
- Grants.gov CSV export used by the page download button: `https://simpler.grants.gov/api/search/export`
- SBA SUBNet opportunities page: `https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities`
- City of Austin solicitations: `https://financeonline.austintexas.gov/afo/account_services/solicitation/solicitations.cfm`
- City of San Antonio bidding and contract opportunities: `https://webapp1.sanantonio.gov/BidContractOpps/Default.aspx`
- Travis County BidNet portal: `https://www.bidnetdirect.com/texas/traviscounty`
- Dallas County BidNet portal: `https://www.bidnetdirect.com/texas/dallas-county/solicitations/open-bids?selectedContent=BUYER`
- Houston METRO procurement opportunities: `https://www.ridemetro.org/about/business-to-business/procurement-opportunities`

The backend uses the same `POST` flow the ESBD site uses for `Export to CSV`, bounded to a weekly window by default. For the federal source, the backend uses the same public JSON listing feed the Acquisition Gateway page and its client-side export use. For Grants.gov, the backend uses the same public CSV export endpoint triggered by the page's `Download all` button. For SBA SUBNet, the backend walks the public paginated HTML table because the page exposes server-rendered opportunity rows rather than a documented download endpoint.

The source registry now keeps a record of every procurement feed in the funnel and records whether each source fully loaded, only exposed a reachable shell, or was blocked by anti-bot protections / iframe embedding. The first parser-backed local sources are:

- City of Austin
- City of San Antonio
- Travis County BidNet
- Dallas County BidNet
- Houston METRO

The first tracked-but-not-fully-loaded sources are:

- City of Fort Worth Bonfire
- City of El Paso Ion Wave
- Harris County Bonfire
- Tarrant County Ion Wave
- Collin County Ion Wave
- Dallas County official purchasing page
- CapMetro PlanetBids
- DART procurement page
- H-GAC OpenGov embed

## Backend API

- `POST /contracts/refresh`
- `POST /contracts/refresh-federal`
- `POST /contracts/refresh-grants`
- `POST /contracts/refresh-sba-subnet`
- `POST /contracts/refresh-tracked-sources`
- `POST /contracts/{id}/funnel`
- `GET /contracts/list?limit=12&matches_only=true&open_only=true&min_priority_score=0`
- `GET /contracts/runs?limit=5`
- `GET /contracts/sources`
- `GET /contracts/export.csv?window_days=7`
- `GET /contracts/export-federal.csv`
- `GET /contracts/export-grants.csv`
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

`POST /contracts/refresh-federal` refreshes the current federal forecast snapshot. It does not take a window payload because the upstream source is a live nationwide forecast list rather than a date-bounded posting feed.

`POST /contracts/refresh-grants` refreshes the current Grants.gov export snapshot. It does not take a window payload because the upstream source is a live nationwide opportunities list rather than a date-bounded posting feed.

`POST /contracts/refresh-sba-subnet` refreshes the current SBA SUBNet paginated listing. It does not take a window payload because the upstream source is a live subcontracting board rather than a date-bounded posting feed.

`POST /contracts/refresh-tracked-sources` refreshes the municipal/county/regional tracked-source batch. Parser-backed sources import opportunities. Harder portals still generate a run record with statuses like `manual_review`, `cataloged`, or `blocked` so the admin UI shows coverage gaps instead of silently dropping them.

The admin app now has a dedicated `Sources` page alongside `Opportunities`. The `Sources` page lists all procurement sources in the funnel and spells out the automation path for each one, including whether it is:

- a full opportunity loader
- a catalog/probe-only integration
- blocked and still needing a deeper browser or portal-specific pass

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

That command now refreshes Texas ESBD, the federal forecast source, Grants.gov, SBA SUBNet, and the tracked municipal/county/regional procurement sources in one run.

Direct command:

```bash
cd backend
python3 -m app.jobs.refresh_gov_contracts --window-days 7
```

Useful variants:

```bash
python3 -m app.jobs.refresh_gov_contracts --window-days 7 --skip-federal
python3 -m app.jobs.refresh_gov_contracts --window-days 7 --skip-grants
python3 -m app.jobs.refresh_gov_contracts --window-days 7 --skip-sba
python3 -m app.jobs.refresh_gov_contracts --window-days 7 --skip-tracked-sources
python3 -m app.jobs.refresh_gov_contracts --window-days 7 --include-gmail --gmail-limit 50
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

Keyword rules control fit matching and can be managed directly from the opportunities page. The default rules are tuned for LeCrown-style work across state, federal, grant, and subcontracting sources, with heavier weight on:

- property management
- real estate
- building or facility maintenance
- construction, renovation, demolition, paving, concrete
- HVAC, electrical, plumbing, landscaping, janitorial
- information technology, managed IT services, cybersecurity
- software development, systems integration, cloud services, network infrastructure

On a fresh install, the platform now seeds those default keyword rules automatically the first time the keyword list is loaded, so the matcher is usable before any manual tuning.

You can still extend the starting keyword set with `GOV_CONTRACT_EXTRA_KEYWORDS` in the environment, but the primary control surface is now the admin-managed keyword rule list.

## Score Matrix

Each stored opportunity now carries a score matrix:

- `Closeness`: normalized keyword-fit score
- `Timing`: due-date runway
- `Competition edge`: broad vs specialized bid heuristics
- `Agency affinity`: boost from preferred agencies
- `Priority`: weighted overall score used for sorting and the minimum-priority filter

Agency preferences are managed separately from keywords and let operators bias the ranked list toward target buyers without removing non-matching opportunities from storage.

## Tracked Source Status

The sources page now includes the full procurement-source registry. Each source records:

- platform type
- jurisdiction class
- whether it is parser-backed or catalog-only
- latest run status
- latest run detail
- current stored opportunity count for that source

This is meant to prevent “false green” coverage. If a portal is JS-only, behind an anti-bot challenge, or hidden in an iframe, the system records that explicitly so it is obvious which sources need a deeper integration pass.

## Funnel Behavior

Matches are not auto-sent to the CRM on refresh.

Current behavior:

- weekly refresh pulls and scores opportunities
- the admin UI shows ranked matches
- an operator can promote a contract into the lead funnel
- promotion creates an intake-style audit record and pushes the lead to `EspoCRM`

This keeps the contract source connected to the lead funnel without spamming the CRM with every weekly match.
