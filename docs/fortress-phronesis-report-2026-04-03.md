# Fortress Phronesis Report

Date: April 3, 2026

LeCrown Platform now has a dedicated government opportunities workflow. Texas ESBD contract ingestion is implemented, scored for fit, stored, and exposed through a standalone Opportunities page in the admin UI. Matching contracts can be pushed into the lead funnel and routed into EspoCRM. The contracts surface is now admin-protected.

## Completed Work

- Added Texas ESBD ingestion, scoring, weekly refresh support, CSV export, and contract storage.
- Added CRM funnel integration so selected opportunities can become leads.
- Split the admin UI so opportunities live on their own page instead of only inside the dashboard.
- Protected the opportunities page and `/contracts/*` endpoints with admin auth.
- Changed the frontend container from a Vite dev server to a production-style static build served by `nginx`.
- Made Gmail RFQ sync optional so environments without that sidecar feed no longer fail against `127.0.0.1:5001`.
- Added a production deployment bundle under `ops/platform` with compose, env template, and nginx configs for `app.lecrowndevelopment.com` and `api.lecrowndevelopment.com`.

## Verified Locally

- Backend compile passed.
- Local Docker stack builds and runs.
- Frontend now serves built static assets.
- Admin auth works for the protected contracts routes.
- Contracts capability endpoint correctly disables Gmail RFQ sync when not configured.

## Production Status

- `app.lecrowndevelopment.com` and `api.lecrowndevelopment.com` now resolve to `89.117.151.145`.
- Production is not fully live yet.
- Both `app` and `api` are still serving the wrong TLS certificate: `chat.askmortgageauthority.com`.
- Both currently return `404 Not Found`, which indicates nginx routing and certificate setup on the host has not been completed for these new domains.
- Server-side deployment could not be completed from this machine because SSH access to `89.117.151.145` is still denied.

## Current Blocker

- Production host access and nginx/certbot cutover are still required.

## Next Steps

1. Gain SSH access to the production server.
2. Deploy the prepared stack from `ops/platform`.
3. Install nginx configs for `app` and `api`.
4. Issue TLS certs for both hostnames.
5. Reload nginx and verify:
   - `https://app.lecrowndevelopment.com/#/opportunities`
   - `https://api.lecrowndevelopment.com/healthz`

Once server access is available, the remaining production work is operational, not feature development.
