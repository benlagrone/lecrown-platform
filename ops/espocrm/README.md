# EspoCRM Ops Stack

This directory contains the deployable `EspoCRM` stack for `lecrown-platform`.

Important boundary:

- same repository: yes
- same application runtime: no

`EspoCRM` is a separate service that this repo can manage operationally.

## Files

- [crm.sh](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/espocrm/crm.sh)
- [docker-compose.yml](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/espocrm/docker-compose.yml)
- [.env.example](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/ops/espocrm/.env.example)

## Quick Start

From the repo root with `make`:

```bash
make crm-init-env
make crm-up
```

Direct script usage:

```bash
bash ops/espocrm/crm.sh init-env
bash ops/espocrm/crm.sh up
```

Local URLs:

- CRM UI: `http://localhost:8080`
- WebSocket: `ws://localhost:8081`

Then sign in with the admin credentials from `ops/espocrm/.env`.

## Command Targets

From the repo root:

```bash
make crm-init-env
make crm-up
make crm-down
make crm-pull
make crm-build
make crm-upgrade
make crm-logs
make crm-ps
```

Notes:

- `crm-pull` fetches updated official images.
- `crm-build` recreates the stack with the current compose config. This stack mostly uses official images rather than local Docker builds.
- `crm-upgrade` follows EspoCRM's recommended `pull` then `up -d` flow.
- The main runtime is pulled from the official `espocrm/espocrm` container image, so yes, this is primarily a pullable container stack.

## Production Shape

Recommended subdomain:

- `crm.lecrowndevelopment.com`

Recommended runtime shape:

- reverse proxy terminates TLS
- proxy `/` to the EspoCRM HTTP service
- proxy `/ws` to the EspoCRM websocket service

If you are using a host-level reverse proxy on the same machine, keep the default bind host:

- `ESPOCRM_BIND_HOST=127.0.0.1`

That exposes EspoCRM only to the local server, while the reverse proxy publishes the public domain.

For production, typical env values become:

```dotenv
ESPOCRM_SITE_URL=https://crm.lecrowndevelopment.com
ESPOCRM_WEB_SOCKET_URL=wss://crm.lecrowndevelopment.com/ws
```

## Operational Notes

- `espocrm-db` holds MariaDB data in the `espocrm-db` named volume.
- `espocrm` and its companion services share the `espocrm` named volume.
- Removing containers with `docker compose down` preserves data.
- Removing volumes will destroy the CRM data.

## Integration Position

This stack does not make `lecrown-platform` a wrapper around the CRM.

Instead:

- `lecrown-platform` remains the content, distribution, and business-logic layer
- `EspoCRM` remains the operational CRM
- the integration point between them should be API-based
