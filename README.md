# LeCrown Platform

Multi-tenant backend and admin surface for:

- `lecrowndevelopment.com`
- `lecrownproperties.com`

The platform keeps content, transformation, distribution, tenant-scoped inquiry handling, and cross-site intake inside one codebase. The current tenant-scoped paths still use `development` or `properties`, while generalized lead ingestion starts at `POST /intake/lead`.

## Structure

```text
backend/
docs/
frontend/
ops/
docker-compose.yml
.env.example
Makefile
README.md
```

## What is implemented

- FastAPI backend with tenant-aware `content`, `inquiry`, `linkedin`, `youtube`, `distribution`, `intake`, and `auth` routes
- Stripe-backed billing API for shared app accounts, checkout, customer portal, webhook sync, and entitlement lookup
- SQLite persistence through SQLAlchemy
- Minimal React admin for creating canonical content, choosing output channels, and viewing property inquiries
- Transform layer that adapts one content record into channel-specific payloads
- LinkedIn publish service wired to tenant-specific organization IDs
- YouTube upload service wired for per-tenant OAuth access or refresh tokens
- Intake pipeline that stores inbound site leads and forwards them to `EspoCRM`
- Video worker client that can call a separate render server over HTTP or run in stub mode

## API overview

- `POST /content/create`
- `GET /content/list?tenant=development|properties`
- `POST /contracts/refresh`
- `POST /contracts/{id}/funnel`
- `GET /contracts/list`
- `GET /contracts/runs`
- `GET /contracts/export.csv`
- `GET|POST|PATCH|DELETE /contracts/keywords`
- `GET|POST|PATCH|DELETE /contracts/agency-preferences`
- `POST /intake/lead`
- `GET /intake/list`
- `POST /inquiry/create`
- `GET /inquiry/list`
- `POST /linkedin/publish`
- `POST /youtube/publish`
- `POST /distribution/publish`
- `POST /auth/login`
- `GET /auth/me`
- `GET|POST /billing/apps`
- `GET /billing/accounts`
- `POST /billing/accounts`
- `GET|POST /billing/accounts/{account_id}/memberships`
- `GET|POST /billing/entitlements`
- `GET|POST /billing/products`
- `GET|POST /billing/prices`
- `POST /billing/checkout/session`
- `POST /billing/portal/session`
- `GET /billing/accounts/{account_id}/entitlements`
- `GET /billing/accounts/{account_id}/subscriptions`
- `POST /billing/webhooks/stripe`
- `GET /healthz`

## Local run

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend/admin
npm install
npm run dev
```

The admin app defaults to `http://localhost:8000` for the API.

Copy `.env.example` to `.env` before running the stack locally.

For production:

- set `VITE_API_BASE_URL` to the public API origin
- set `CORS_ORIGINS` to the public admin origin
- replace the default `SECRET_KEY` and `ADMIN_PASSWORD`
- set `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and `BILLING_SERVICE_KEYS` before enabling billing flows
- leave `GMAIL_RFQ_FEED_URL` blank unless the Gmail RFQ sidecar service exists in that environment

## Content model shape

Canonical content is stored once and carries distribution intent plus media state:

```json
{
  "tenant": "development",
  "type": "insight",
  "title": "Why warehouse operations break down",
  "body": "Communication failures create delays and cost leakage.",
  "tags": ["operations", "industrial"],
  "distribution": {
    "linkedin": true,
    "youtube": true,
    "website": true,
    "twitter": false
  },
  "media": {
    "video_generated": false,
    "video_path": "/videos/warehouse.mp4",
    "video_url": null,
    "render_status": null,
    "render_job_id": null,
    "youtube_video_id": null,
    "youtube_status": null
  }
}
```

## Docker run

```bash
docker compose up --build
```

Backend: [http://localhost:8000](http://localhost:8000)

Frontend: [http://localhost:3000](http://localhost:3000)

The Docker frontend image now builds static assets and serves them through `nginx`, which is suitable for production-style deployments.

## Distribution flow

The platform now follows:

```text
content -> transform -> distribute
```

Current channel support:

- `linkedin`: implemented
- `youtube`: implemented
- `website`: placeholder response in the distribution controller
- `twitter`: stub publisher placeholder

Video generation ownership:

- The API orchestrates render requests.
- A separate worker is expected to produce the video.
- The backend can call that worker over HTTP through [backend/app/services/video_client.py](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/backend/app/services/video_client.py).

## MediaStudio APIs

`MediaStudio` is now documented as an external API suite that `lecrown-platform` can use for media generation and rendering.

See:

- [docs/mediastudio-apis.md](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/mediastudio-apis.md)

Current stance:

- preferred render worker target: `rs-video-stitch`
- faster all-in-one media backend: `video-gen`
- supporting narration backend: `audio_xtts`
- supporting music backend: `musicService`

## Intake Hub

`lecrown-platform` now includes the first platform-owned cross-site intake route:

- `POST /intake/lead`

Current behavior:

- accepts a source-aware lead payload from an external site
- stores the raw submission in the platform database
- stores a normalized internal representation
- forwards the mapped lead to `EspoCRM`
- stores downstream delivery status and response metadata

Current first target:

- `AskMortgageAuthority`

## Billing API

`lecrown-platform` now exposes a platform billing surface for other LeCrown apps.

Current implementation:

- platform-owned `accounts`, `account_memberships`, `products`, `prices`, `entitlements`, `billing_customers`, `billing_subscriptions`, and `billing_webhook_events`
- hosted Stripe Checkout Session creation for subscription signup
- Stripe Customer Portal session creation for self-service billing management
- webhook-driven subscription synchronization into account-scoped entitlements
- app-scoped entitlement lookup for runtime enforcement in external projects

App-facing billing routes expect:

- `X-Billing-App: <app_key>`
- `X-Billing-Key: <shared_secret>`

`BILLING_SERVICE_KEYS` should be configured as comma-separated `app_key:secret` pairs.

## Feature Roadmap

Product direction:

- `lecrown-platform` should become the internet publishing focal point
- the publishing surface should cover blogs, `Twitter/X`, and other social sites
- multi-account publishing should be a first-class capability across brands, pages, sites, and operator accounts
- it should also act as the capture point for forms across different sites and funnel those submissions into the CRM

See:

- [docs/feature-roadmap.md](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/feature-roadmap.md)
- [docs/billing-platform-strategy.md](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/billing-platform-strategy.md)
- [docs/lecrown-billing-workflow-spec.md](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/lecrown-billing-workflow-spec.md)

## CRM Direction

`lecrown-platform` should not be treated as the final cross-business CRM.

Current position:

- keep the built-in `/inquiry` flow narrow and tenant-specific
- use `EspoCRM` as the shared operational CRM across businesses
- integrate with CRM over API boundaries instead of rebuilding everything in this repo too early

See:

- [docs/espocrm-strategy.md](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/espocrm-strategy.md)

This is especially important because the current inquiry model is still `properties`-specific, while the CRM direction now spans:

- `LeCrown Properties`
- `AskMortgageAuthority`
- future businesses

## Site Integration References

Other sites should integrate against shared APIs, not shared folders or direct code imports.

Reference docs:

- [Site Integration Overview](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/site-integration-overview.md)
- [Site API Reference](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/site-api-reference.md)
- [Site Integration Checklist](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/site-integration-checklist.md)
- [AskMortgageAuthority Integration](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/askmortgageauthority-integration.md)
- [Intake Architecture](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/intake-architecture.md)

## CRM Ops Stack

This repo now includes a dedicated EspoCRM deployment stack under:

- [ops/espocrm](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/espocrm)

Use it as:

- same repository
- separate service

## Government Contracts

`lecrown-platform` can now ingest Texas ESBD opportunities, score likely-fit government work, and expose both ranked matches and a weekly CSV export through the admin surface and backend API.

The opportunities page now supports:

- admin auth
- keyword rule management
- agency preference management
- complete-list storage with view-only filters
- a score matrix built from closeness, timing, competition edge, and agency affinity

See:

- [docs/gov-contracts.md](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/gov-contracts.md)
- separate runtime boundary

Repo-level commands:

```bash
make crm-init-env
make crm-up
make crm-pull
make crm-build
make crm-upgrade
make crm-logs
make crm-ps
make crm-down
```

Direct script entrypoint:

```bash
./ops/espocrm/crm.sh help
```

Recommended production subdomain:

- `crm.lecrowndevelopment.com`

## First milestone flow

1. Create a content item through `POST /content/create` or the admin UI.
2. Confirm it was stored with `GET /content/list?tenant=...`.
3. Set `LINKEDIN_TOKEN` plus the tenant org IDs in `.env`.
4. Publish with `POST /linkedin/publish`.
5. Verify the post on the matching LinkedIn organization page.

## YouTube publish flow

Use one of these credential paths per tenant:

- Set `YOUTUBE_ACCESS_TOKEN_DEV` or `YOUTUBE_ACCESS_TOKEN_PROP` directly.
- Or set `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and the tenant refresh token so the backend can mint an access token at publish time.

Example direct upload:

```json
{
  "tenant": "development",
  "title": "Why warehouse operations break down",
  "description": "A direct explanation of the operational failure pattern.",
  "video_path": "/videos/warehouse.mp4",
  "tags": ["property management", "warehouse"]
}
```

Example orchestrated distribution:

```json
{
  "content_id": "123",
  "channels": ["linkedin", "youtube"],
  "video_style": "corporate_clean",
  "youtube_video_path": "/videos/warehouse.mp4"
}
```

If `youtube_video_path` is omitted, the distribution service will ask the video worker to render one.

## Video worker integration

By default the platform runs in `VIDEO_RENDER_MODE=stub`, which is the safe development path while the worker contract is still being finalized.

To use an HTTP render worker:

1. Set `VIDEO_RENDER_MODE=http`
2. Set `VIDEO_SERVER_URL` to the worker base URL
3. Optionally change `VIDEO_RENDER_ENDPOINT` and `VIDEO_RENDER_DEFAULT_STYLE`

Expected worker request:

```json
{
  "content_id": "123",
  "script": "Why warehouse operations break down...",
  "title": "Why warehouse operations break down",
  "tenant": "development",
  "style": "corporate_clean",
  "tags": ["operations", "industrial"]
}
```

Expected worker response:

```json
{
  "status": "complete",
  "job_id": "job_123",
  "video_path": "/shared/outputs/video_123.mp4",
  "video_url": "http://100.x.x.x:8001/files/video_123.mp4"
}
```

Notes:

- `video_path` only works if the platform can read that path locally or via a shared mount.
- `video_url` is the safer cross-machine contract; the backend will download it temporarily before uploading to YouTube.
- Tailscale is the simplest way to make the worker reachable without exposing it publicly.

## Example payloads

### Create content

```json
{
  "tenant": "development",
  "type": "linkedin_post",
  "title": "A sharper acquisition lens",
  "body": "We underwrite deals by pressure-testing downside first.",
  "tags": ["acquisitions", "strategy"],
  "publish_linkedin": true,
  "publish_site": true
}
```

### Create inquiry

```json
{
  "tenant": "properties",
  "asset_type": "multifamily",
  "location": "Houston, TX",
  "problem": "Occupancy dropped after deferred maintenance piled up.",
  "contact_name": "Jordan Smith",
  "email": "jordan@example.com",
  "phone": "713-555-0199"
}
```

### Intake lead

```json
{
  "source_site": "askmortgageauthority.com",
  "source_type": "wordpress",
  "form_provider": "WPForms",
  "form_id": "12",
  "external_entry_id": "481",
  "page_url": "https://askmortgageauthority.com/get-pre-qualified/",
  "business_context": "AskMortgageAuthority",
  "product_context": "Mortgage",
  "metadata": {
    "campaign": "spring-search"
  },
  "lead": {
    "firstName": "Jordan",
    "lastName": "Smith",
    "emailAddress": "jordan@example.com",
    "phoneNumber": "713-555-0199",
    "description": "Looking to get pre-qualified.",
    "source": "Website"
  }
}
```

If `INTAKE_API_KEY` is configured, send:

- header `X-Intake-Key: <INTAKE_API_KEY>`

Relevant environment variables:

```dotenv
INTAKE_API_KEY=
ESPOCRM_BASE_URL=https://crm.lecrowndevelopment.com
ESPOCRM_API_KEY=
ESPOCRM_USERNAME=
ESPOCRM_PASSWORD=
ESPOCRM_TIMEOUT_SECONDS=15
```

## Notes

- Inquiry capture is restricted to the `properties` tenant.
- `POST /intake/lead` is the cross-site intake boundary; `/inquiry` is still the older tenant-specific path.
- Auth exists as a thin admin stub. Content and inquiry routes are not gated yet.
- `GET /intake/list` is gated through the current admin bearer token flow.
- `ai_video_service.py` now orchestrates remote rendering through `video_client.py` instead of assuming the API renders media itself.
- In `stub` mode, you still need to provide a usable `VIDEO_STUB_VIDEO_PATH`, `VIDEO_STUB_VIDEO_URL`, or a manual `youtube_video_path` if you want YouTube upload to succeed end-to-end.
