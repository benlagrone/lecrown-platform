# Government Contracts

The platform can now pull Texas ESBD opportunities from `txsmartbuy.gov`, federal forecast opportunities from `acquisitiongateway.gov`, grant opportunities from `simpler.grants.gov`, SBA SUBNet subcontracting opportunities from `sba.gov`, Gmail RFQs from the configured RFQ label feed, and a first wave of municipal/county/regional Texas procurement sources, rank them against LeCrown-relevant work, and surface the strongest matches in the admin app.

## Source

### EspoCRM Source Catalog

When EspoCRM is configured, `POST /contracts/refresh-tracked-sources`, the tracked-source
step of `POST /contracts/refresh-all`, and `app.jobs.refresh_gov_contracts` read the
complete paginated EspoCRM Account catalog before searching portals. The existing
Sources and Opportunities pages display the resulting coverage and scored records.
This direction is **CRM to platform**: the refresh does not write Accounts, enroll
vendors, log in to buyer portals, or create CRM opportunities.

- `GOV_CONTRACT_SOURCE_CATALOG=auto` (default) selects CRM when its URL or credentials
  are present; otherwise the original static registry remains available.
- `GOV_CONTRACT_SOURCE_CATALOG=espocrm` requires CRM and fails closed on missing or
  invalid configuration. Use this setting for the Development deployment.
- `GOV_CONTRACT_SOURCE_CATALOG=static` explicitly selects the legacy registry.
- Configure `ESPOCRM_BASE_URL` plus `ESPOCRM_API_KEY`, or `ESPOCRM_USERNAME` and
  `ESPOCRM_PASSWORD`. `ESPOLOGIN` and `ESPOPW` are supported aliases. Secrets must be
  injected server-side; this app never reads another project's environment file.

Source Accounts use the procurement classification descriptions maintained by the
`espocrm-procurement-sources` skill. Ordinary customer Accounts are excluded. Account
IDs preserve identity across edits; normalized listing URLs deduplicate sources and
preserve legacy source keys. JAGGAER `CustomerOrg` remains part of URL identity.
Deleted/unclassified sources become inactive after a complete successful snapshot;
historical opportunities are retained. An empty, incomplete, or failed catalog read
retains the previous snapshot and records a failed `espocrm_catalog` run, without
searching stale sources. Core ESBD, federal, grants, SBA and Gmail feeds remain separate.

Buyer-specific Bonfire portals use the public JSON listing adapter, excluding private
projects. Existing dedicated buyer adapters remain available for exact recognized URLs.
Bonfire refreshes are idempotent, and records absent from a successful complete open
snapshot are marked closed. Unsupported portals report `manual_review`; registration-only
and overlap records report `cataloged`, not a successful search. Public adapter requests
do not follow redirects or receive CRM credentials. A reachable portal does not establish
document access, eligibility, qualification, or successful bid submission.

Bonfire enforces shared rate limits across buyer hosts. Public imports are paced by
`GOV_CONTRACT_PORTAL_INTERVAL_SECONDS` (default 6 seconds), with at most
`GOV_CONTRACT_PORTAL_BATCH_SIZE` (default 10) attempts per refresh. Never-attempted and
oldest-attempted buyers go first, so repeated runs cover the full catalog rather than
repeating its alphabetic beginning. HTTP 429 records a blocked run, persists the
`Retry-After` cooldown, and defers remaining Bonfire requests. Deferred sources are
not counted as searched. Scheduled CLI runs should repeat until the catalog is covered;
the importer itself does not install a schedule. Failed or blocked imports produce a
nonzero CLI exit status.

The refresh is a potentially long-running multi-source batch. Use the existing CLI job
for scheduled full-catalog runs; the synchronous API must have a sufficient request
timeout. Check `/contracts/runs` for per-source failures, not just HTTP success.
Deployment still requires a Development-owned target through the workspace deployment
runway; the Properties compatibility publishing workflow is not this release path.

- public ESBD page: `https://www.txsmartbuy.gov/esbd`
- ESBD service used by the site export: `https://www.txsmartbuy.gov/app/extensions/CPA/CPAMain/1.0.0/services/ESBD.Service.ss`
- public federal forecast page: `https://acquisitiongateway.gov/forecast`
- federal forecast JSON feed used by the site listing and CSV export batching: `https://ag-dashboard.acquisitiongateway.gov/api/v3.0/resources/forecast?_format=json`
- public grants search page: `https://simpler.grants.gov/search`
- Grants.gov CSV export used by the page download button: `https://simpler.grants.gov/api/search/export`
- SBA SUBNet opportunities page: `https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities`
- Gmail RFQ label feed: `GMAIL_RFQ_FEED_URL` with label `RFQs` by default
- City of Austin solicitations: `https://financeonline.austintexas.gov/afo/account_services/solicitation/solicitations.cfm`
- City of San Antonio bidding and contract opportunities: `https://webapp1.sanantonio.gov/BidContractOpps/Default.aspx`
- Travis County BidNet portal: `https://www.bidnetdirect.com/texas/traviscounty`
- Dallas County BidNet portal: `https://www.bidnetdirect.com/texas/dallas-county/solicitations/open-bids?selectedContent=BUYER`
- Houston METRO procurement opportunities: `https://www.ridemetro.org/about/business-to-business/procurement-opportunities`

The backend uses the same `POST` flow the ESBD site uses for `Export to CSV`, bounded to a weekly window by default. For the federal source, the backend uses the same public JSON listing feed the Acquisition Gateway page and its client-side export use. For Grants.gov, the backend uses the same public CSV export endpoint triggered by the page's `Download all` button. For SBA SUBNet, the backend walks the public paginated HTML table because the page exposes server-rendered opportunity rows rather than a documented download endpoint.

The source registry now contains 48 resources: 19 original opportunity-source definitions plus 29 buyer,
registration, certification, subcontracting, advisory, and supplier-diversity references recovered from the
Metro LeCrown operating trackers and the government-contracting knowledge package. The registry records whether
each opportunity source fully loaded, only exposed a reachable shell, or was blocked by anti-bot protections /
iframe embedding. Reference resources remain catalog entries unless a tested loader exists. The first parser-backed
local sources are:

- City of Austin
- City of San Antonio
- Travis County BidNet
- Dallas County BidNet
- Houston METRO
- DART Bonfire public opportunities (JSON import)

The first tracked-but-not-fully-loaded sources are:

- City of Fort Worth Bonfire
- City of El Paso Ion Wave
- Harris County Bonfire
- Tarrant County Ion Wave
- Collin County Ion Wave
- Dallas County official purchasing page
- CapMetro PlanetBids
- H-GAC OpenGov embed

## Backend API

### Local Candidate Inbox and Explicit Promotion

Set `PROCUREMENT_CANDIDATE_JSON_PATH` to a durable, private, server-local file.
Discovery writes deduplicated candidate snapshots to that JSON file; the SQL tables
remain the search/scoring projection for the existing UI. Collection never creates
EspoCRM Leads or Opportunities. The file is atomically replaced, fsynced, mode 0600,
and guarded by inter-process locks. Corrupt files fail closed rather than being reset.

The Opportunities page is a candidate inbox. `Select for EspoCRM` opens a review form;
only `Create EspoCRM Opportunity` submits the chosen candidate. EspoCRM requires an
estimated USD amount and expected close date. Neither is invented by the importer;
the displayed solicitation deadline must be reviewed before using it as a close date.
The legacy Lead funnel API remains for compatibility but is no longer the inbox action.

- `GET /contracts/candidates/export.json` downloads the private JSON inbox (admin only).
- `POST /contracts/{id}/promote` requires admin access and `confirmed: true`, `amount`,
  `close_date`, optional `stage` and `notes`. It creates an EspoCRM `Opportunity`, not a Lead.
- The JSON promotion receipt is written before sending. A stable source-key marker
  reconciles existing CRM records. Uncertain writes are never blindly retried; known
  record IDs are read back and verified before reporting success.
- Recollection preserves promotion receipts and updates discovery metadata without
  creating another CRM record. Existing source snapshots are retained across restarts.
- `app.jobs.collect_procurement_candidates` runs bounded CRM-source batches every
  `PROCUREMENT_COLLECTION_INTERVAL_SECONDS` (default 900). It does not promote records.
  A shared collection lock prevents overlap with manual refreshes.

The separate Development deployment stores the inbox at
`/app/data/procurement-candidates.json` in `lecrown_development_data`.
See [Development deployment](development-deployment.md) for the locked runway,
source publication, credentials, verification, and rollback boundaries.

- `POST /contracts/refresh`
- `POST /contracts/refresh-federal`
- `POST /contracts/refresh-grants`
- `POST /contracts/refresh-sba-subnet`
- `POST /contracts/refresh-gmail`
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

`POST /contracts/refresh-gmail` checks the Gmail RFQ source every time it is requested. If `GMAIL_RFQ_FEED_URL` is configured, it imports RFQ messages from that feed. Otherwise it uses the configured Google OAuth refresh token to search Gmail directly for `label:rfqs`, requests up to 5,000 messages, and splits digest emails with multiple bid links into separate opportunity records. If neither the feed nor Gmail OAuth is configured, it records a `manual_review` source run instead of hiding Gmail RFQs from the source list.

`POST /contracts/refresh-tracked-sources` refreshes the municipal/county/regional tracked-source batch. Parser-backed sources import opportunities. Harder portals still generate a run record with statuses like `manual_review`, `cataloged`, or `blocked` so the admin UI shows coverage gaps instead of silently dropping them.

The admin app now has a dedicated `Sources` page alongside `Opportunities`. The `Sources` page lists the full
government-contracting resource catalog, groups it by purpose, and spells out the automation path for each one,
including whether it is:

- a full opportunity loader
- a catalog/probe-only integration
- a buyer-registration, certification, subcontracting, advisory, or supplier-diversity reference
- blocked and still needing a deeper browser or portal-specific pass

The admin app also has a dedicated `Certifications` page at `#/certifications`.
As of the July 24, 2026 B2Gnow portal check, LeCrown Development Corporation
has active Houston METRO SBE certification effective 2026-07-15 with renewal
due 2029-07-15. City of Houston OBO application `6369689` is incomplete at 52%
for MBE/WBE/SBE/PDBE New Application. The application cannot be signed or
submitted yet because six form sections are incomplete and the document tab
shows `0 attached of 13 mandatory; 0 attached of 13 required`. Credentials must
stay out of tracked files and should live only in the private credential store.

The Certifications page includes a recent activity feed for status changes and
follow-ups plus a City of Houston blocker panel with the six incomplete form
sections and 13 mandatory documents. The first activity records mirror the Metro
LeCrown tracker activity CSV at
`/Users/benjaminlagrone/Documents/projects/metroLecrown/data/certification-activity.csv`.

## Knowledge and Operating Playbook

The tracked government-contracting knowledge package now includes the original
UH APEX materials, a source/freshness inventory, a certification and
market-access map, and a 90-day operating plan:

- [Government Contracting Knowledge Base](./government-contracting/README.md)
- [Subcontracting and Market-Access Plan](./government-contracting/subcontracting-market-access-plan.md)
- [Original source materials](./government-contracting/source-materials/)

The source materials are reference evidence, not live proof of current program
rules. The knowledge base links to official program pages and records the
required verification boundary. Credentials and sensitive certification
evidence must remain outside Git.

The tracker reconciliation uses the links already supplied in:

- `/Users/benjaminlagrone/Documents/projects/metroLecrown/data/buyers.csv`
- `/Users/benjaminlagrone/Documents/projects/metroLecrown/data/buyer-certification-requirements.csv`
- `/Users/benjaminlagrone/Documents/projects/metroLecrown/data/company-certifications.csv`
- `/Users/benjaminlagrone/Documents/projects/metroLecrown/data/certification-steps.csv`

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

That command now refreshes Texas ESBD, the federal forecast source, Grants.gov, SBA SUBNet, Gmail RFQs, and the tracked municipal/county/regional procurement sources in one run.

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
python3 -m app.jobs.refresh_gov_contracts --window-days 7 --skip-gmail
python3 -m app.jobs.refresh_gov_contracts --window-days 7 --skip-tracked-sources
python3 -m app.jobs.refresh_gov_contracts --window-days 7 --gmail-limit 50
```

Example cron entry for every Monday at 8:00 AM server local time:

```cron
0 8 * * 1 cd /Users/benjaminlagrone/Documents/projects/metroLecrown/platform/backend && /usr/bin/python3 -m app.jobs.refresh_gov_contracts --window-days 7
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

## Tracked Resource Status

The sources page now includes the full opportunity and business-development resource registry. Each resource records:

- platform type
- jurisdiction class
- resource type
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
