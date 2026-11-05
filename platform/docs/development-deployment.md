# Development Deployment

Deployment authority is `workspace-deployment/locks/lecrown-development.yaml`.
Operational implementation is owned by Fortress Phronesis at
`ops/lecrown-development/`; this repository supplies a committed source archive only.

## Isolation Contract

- Public app: `https://app.lecrowndevelopment.com/`.
- Public API: `https://api.lecrowndevelopment.com/` (browser calls use same-origin `/api`).
- Development Compose project/network: `lecrown-development` / `lecrown-development-net`.
- New loopback app/API ports: `13095` / `18045`.
- Old shared app/API ports: `13084` / `18035`, retained unchanged for Properties.
- Persistent volume: `lecrown_development_data`, with its own database and candidate JSON.
- Runtime settings are private server-side JSON managed by the runway, not a shared `.env`.
- No Properties database, credentials, volumes, or container are copied or restarted.

The new Development administrator uses the explicitly supplied Development environment
file's `ADMIN_USERNAME` and `ADMIN_PASSWORD`, not the Properties database's users.
EspoCRM credentials are injected only into backend/collector/pursuit-ranker containers.

## Release

1. Validate with `scripts/platform.sh verify`.
2. Commit the reviewed source files. The runway archives only `platform/backend` and
   `platform/frontend` from that exact Git commit; ignored environments and local data
   are never included. No registry permission or GitHub account changes are required.
3. Run the workspace lock validator and the Fortress-owned deploy command documented in
   `ops/lecrown-development/README.md`. It builds SHA-tagged images on the deployment host,
   validates their revision labels, backs up the two Development nginx vhosts, and checks
   the new loopback runtime before cutover.
4. Verify both public Development routes, authenticated Sources/candidate export, and
   unchanged Properties container IDs and public health. A code build is not deployment proof.

## Candidate Operations

The collector requests at most 10 Bonfire buyers per batch, at least six seconds apart,
then waits 15 minutes. Unsupported sources remain visible as manual review. HTTP 429
persists a cooldown and defers subsequent requests. Candidate JSON is private and
downloadable only through the authenticated admin export; selection is the only path
that creates an EspoCRM Opportunity. No test candidate should be promoted to live CRM.

## Automatic Pursuit Ranking

Before: existing records were scored only by the explicit manual CLI.
After: a portless `pursuit-ranker` service in the same locked project checks CRM
every 60 seconds and updates only existing scoring fields. The same AI-first,
prime-first model applies, without assumed software contractor costs. It reuses
the collector's complete public snapshots for deadline changes and recalculates
date-sensitive readiness/expiry daily. No new secrets, ports, networks or volume
are introduced; private state lives at `/app/data/crm-pursuit-scoring`.
Deployment checks a successful CRM read/write/readback pass and worker health;
rollback removes the worker if the prior release did not define it.

## Semantic Lead Qualification

Before: title-token overlap generalized High/Low-fit feedback.
After: the portless `semantic-qualifier` worker uses local BGE-small neural
embeddings and a supervised logistic classifier trained on the current ratings.
Complete captured descriptions are token-chunked without truncation. A versioned
LeCrown capability gate covers custom software/platforms, AI/ML, data, cloud/security,
digital workflows and new-energy project leadership/integration. Roads, real estate,
commodity supply, lobbying and grant applications cannot qualify merely by matching
a rated title. Explicit human labels remain authoritative and are never overwritten.

The worker rechecks data/ratings every cycle, using private vector caches/projections
in `/app/data/semantic-fit`. It checks public descriptions in bounded five-record
batches at six-second spacing under the collector's lock and shared 429 cooldown.
Ordinary headless public navigation is a fallback when a page needs JavaScript;
there is no login, stealth mode, proxy rotation or CAPTCHA solving. Blocked pages
remain visible. Missing substantive descriptions and ambiguous/staffing-heavy scopes
require review, rather than silently falling back to title qualification.

Where a public portal serves a normal browser but blocks the server-side worker,
an administrator can submit up to 100 observed public Bonfire descriptions to
`POST /contracts/descriptions/public-browser` as `{ "items": [{ "source_url":
"https://buyer.bonfirehub.com/opportunities/123", "text": "..." }] }`. Each URL
must exactly match an existing candidate; the endpoint cannot fetch private pages
or create CRM records. It records browser provenance, preserves previous scope in
bounded history, and retains fit ratings and promotion receipts. The worker skips
these successful captures and rebuilds qualification on the next cycle. Public
pages that provide only a title remain unqualified, and this browser-assisted path
is not a claim of autonomous coverage for every registered source.

The v2 capability gate requires corroborating delivery evidence in the full
description as well as the trained semantic score. Informational RFIs and
resale-only notices stay review items, not prime-bid matches. Human ratings still
override this automated decision for their own records.

Grouped out-of-fold label diagnostics choose a conservative positive threshold;
these are not calibrated fit or win probabilities or independent acceptance evidence.
The UI shows source descriptions, model state, training/coverage counts and related
examples. A changed rating or source text invalidates affected stale decisions.
This feature does not change credentials, CRM promotion rules or pursuit-score weights.
The runtime adds no ports or secrets; the image bundles the local model and Chromium.

## Rollback

Use the Fortress-owned rollback operation and its recorded release backup. Restore
only the two Development vhost backups and, for an existing Development release, its
previous image pins. For an initial split, stop only the `lecrown-development` project
without removing its volume. Properties remains on the original containers and ports.
