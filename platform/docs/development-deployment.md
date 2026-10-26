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
EspoCRM credentials are injected only into backend/collector containers.

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

## Rollback

Use the Fortress-owned rollback operation and its recorded release backup. Restore
only the two Development vhost backups and, for an existing Development release, its
previous image pins. For an initial split, stop only the `lecrown-development` project
without removing its volume. Properties remains on the original containers and ports.
