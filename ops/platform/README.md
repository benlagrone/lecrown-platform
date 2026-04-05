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
- explicit public app and API hostnames

## Expected Hostnames

- `app.lecrowndevelopment.com`
- `api.lecrowndevelopment.com`

## Expected DNS

Both hostnames should resolve to the production server IP before you deploy:

- `89.117.151.145`

Recommended records:

```text
app.lecrowndevelopment.com.  A  89.117.151.145
api.lecrowndevelopment.com.  A  89.117.151.145
```

## Files

- [docker-compose.prod.yml](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/docker-compose.prod.yml)
- [.env.example](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/.env.example)
- [nginx.app.lecrowndevelopment.com.conf](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/nginx.app.lecrowndevelopment.com.conf)
- [nginx.api.lecrowndevelopment.com.conf](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/nginx.api.lecrowndevelopment.com.conf)

## Runtime Shape

- backend listens on `127.0.0.1:8000`
- frontend listens on `127.0.0.1:3000`
- host-level `nginx` terminates TLS and proxies:
  - `app.lecrowndevelopment.com` -> `127.0.0.1:3000`
  - `api.lecrowndevelopment.com` -> `127.0.0.1:8000`

## Environment

Copy [.env.example](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/platform/.env.example) to `ops/platform/.env` and set real values before bringing the stack up.

Important production values:

- `VITE_API_BASE_URL=https://api.lecrowndevelopment.com`
- `CORS_ORIGINS=https://app.lecrowndevelopment.com`
- `SECRET_KEY` must be replaced
- `ADMIN_PASSWORD` must be replaced
- `DATABASE_URL=sqlite:///./data/lecrown.db`
- leave `GMAIL_RFQ_FEED_URL` blank unless that service exists on the server

## Deploy

From the repository root on the server:

```bash
docker compose -f ops/platform/docker-compose.prod.yml --env-file ops/platform/.env up -d --build
```

## TLS

The nginx configs in this folder expose `/.well-known/acme-challenge/` for certificate issuance.

If the server already follows the same pattern as `crm.lecrowndevelopment.com`, install the two site configs and obtain certs for:

- `app.lecrowndevelopment.com`
- `api.lecrowndevelopment.com`

## Verification

After deploy:

```bash
curl -I https://app.lecrowndevelopment.com
curl https://api.lecrowndevelopment.com/healthz
```

Then sign in on the opportunities page with the production admin credentials from `ops/platform/.env`.
