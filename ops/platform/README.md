# LeCrown Platform Ops

This directory contains the production-oriented runtime shape for `lecrown-platform`.

Important boundary:

- same repository: yes
- same runtime as `EspoCRM`: no
- same production host: possible

The local root `docker-compose.yml` is useful for development. The files here are for a production-style deployment with:

- private loopback binds
- public `nginx` reverse proxy in front
- persistent SQLite storage
- a canonical same-origin back-office hostname
- a retained API hostname for approved non-browser integrations

## Canonical Hostnames

- `backoffice.lecrownproperties.com`
- `api.lecrowndevelopment.com`

The back-office browser uses `https://backoffice.lecrownproperties.com/api/*`.
Host-level nginx strips `/api/` and proxies to the private backend. The separate
API hostname may remain for approved site-to-platform integrations, but the
back-office frontend does not depend on cross-origin API access.

## Expected DNS

The canonical back-office hostname must resolve to the production server IP
before TLS activation:

- `89.117.151.145`

Recommended records:

```text
backoffice.lecrownproperties.com.  A  89.117.151.145
api.lecrowndevelopment.com.  A  89.117.151.145
```

## Files

- [docker-compose.prod.yml](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/docker-compose.prod.yml)
- [.env.example](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/.env.example)
- [nginx.backoffice.lecrownproperties.com.conf](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/nginx.backoffice.lecrownproperties.com.conf)
- [install-backoffice-vhost.sh](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/install-backoffice-vhost.sh)
- [nginx.app.lecrowndevelopment.com.conf](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/nginx.app.lecrowndevelopment.com.conf)
- [nginx.api.lecrowndevelopment.com.conf](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/nginx.api.lecrowndevelopment.com.conf)
- [verify-backoffice.sh](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/verify-backoffice.sh)

The older `app.lecrowndevelopment.com` config is retained only for an orderly
transition. Do not make it the canonical user-facing URL.

## Runtime Shape

- backend listens on `127.0.0.1:18035`
- frontend listens on `127.0.0.1:13084`
- host-level `nginx` terminates TLS and proxies:
  - `backoffice.lecrownproperties.com/` -> `127.0.0.1:13084`
  - `backoffice.lecrownproperties.com/api/` -> `127.0.0.1:18035/`
  - `api.lecrowndevelopment.com` -> `127.0.0.1:18035`

## Environment

Copy [.env.example](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/.env.example) to `ops/platform/.env` and set real values before bringing the stack up.

`ops/platform/.env` is intentionally gitignored. Keep it only on the server or in your local untracked deploy workspace.

Important production values:

- `VITE_API_BASE_URL=/api`
- `PUBLIC_APP_URL=https://backoffice.lecrownproperties.com`
- `CORS_ORIGINS=https://backoffice.lecrownproperties.com`
- `ALLOWED_HOSTS` must include `backoffice.lecrownproperties.com`
- `DOCUMENT_STORAGE_DIR=/app/data/documents`
- `PLATFORM_API_BIND=127.0.0.1:18035`
- `PLATFORM_FRONTEND_BIND=127.0.0.1:13084`
- `SECRET_KEY` must be replaced
- `ADMIN_PASSWORD` must be replaced
- `ADMIN_EMAIL` should be set to the real admin mailbox
- `DATABASE_URL=sqlite:///./data/lecrown.db`
- `ESPOCRM_API_KEY` or `ESPOCRM_USERNAME` and `ESPOCRM_PASSWORD` must be set or CRM delivery will stay disconnected
- invite emails require `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `INVITE_SENDER_EMAIL`, and a matching Gmail refresh token
- leave `GMAIL_RFQ_FEED_URL` blank unless that service exists on the server

## Deploy

From the repository root on the server:

```bash
docker compose -f ops/platform/docker-compose.prod.yml --env-file ops/platform/.env up -d --build
```

## Git-To-Prod Path

The repo now has two distinct deployment paths:

- local/server-side manual path: use `ops/platform/docker-compose.prod.yml`
- Git-driven production path: push to `main`, publish GHCR images, then deploy
  the pinned `sha-...` images to production from this repo's workflow

For pushes to `main`, this path now targets `prod` and runs public smoke checks
against:

- `https://backoffice.lecrownproperties.com/`
- `https://backoffice.lecrownproperties.com/api/healthz`

After the private container health checks pass, the direct production workflow
also installs the back-office nginx site and obtains or renews its Let's Encrypt
certificate before running those public checks.

The Git-driven path depends on:

- `.github/workflows/publish-images.yml`
- either source repo deploy secrets `LECROWNPLATFORM_*` or fallback `SOLOMONIC_CLOCK_*`
- or `FORTRESS_REPO_DISPATCH_TOKEN` for fortress-side dispatch fallback

When source-side SSH deploy secrets are present, the workflow deploys directly
from this repo. When they are absent but `FORTRESS_REPO_DISPATCH_TOKEN` exists,
the workflow falls back to dispatching the fortress deploy workflow.


## TLS

The nginx configs in this folder expose `/.well-known/acme-challenge/` for certificate issuance.

If the server already follows the same pattern as `crm.lecrowndevelopment.com`,
install the back-office site config and obtain a certificate for:

- `backoffice.lecrownproperties.com`

Keep the existing API certificate only while that separate integration hostname
is still in use.

On the production host, after the code checkout is current:

```bash
sudo ./ops/platform/install-backoffice-vhost.sh
sudo certbot --nginx -d backoffice.lecrownproperties.com
```

The installer validates nginx before reloading it. Certbot must wait until the
DNS record resolves publicly to the production server.

## Verification

After deploy:

```bash
./ops/platform/verify-backoffice.sh https://backoffice.lecrownproperties.com
```

Then sign in on the opportunities page with the production admin credentials from `ops/platform/.env`.
