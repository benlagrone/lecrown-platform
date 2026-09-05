# Project Agent Instructions

This project is part of the workspace at `/Users/benjaminlagrone/Documents/projects`.

Before editing, read:

- `/Users/benjaminlagrone/Documents/projects/AGENTS.md`
- `/Users/benjaminlagrone/Documents/projects/.workspace/README.md`
- `/Users/benjaminlagrone/Documents/projects/.workspace/projects.json`
- this project's `README.md` and `docs/` files, if present

Use `/Users/benjaminlagrone/Documents/projects/.workspace/bin/context metroLecrown`
when cross-project routing or related context matters.

## Deployment Gate

For any deploy, release, rollback, production, staging, Contabo, VPS, GHCR,
Docker Compose, nginx, TLS, domain, public port, or runtime environment work,
read and follow:

- `/Users/benjaminlagrone/Documents/projects/.workspace/deployment-policy.md`
- `/Users/benjaminlagrone/Documents/projects/pericopeai.com/fortress-phronesis/AGENTS.md`
- `/Users/benjaminlagrone/Documents/projects/pericopeai.com/fortress-phronesis/docs/workspace-contabo-deployment-contract.md`

Fortress Phronesis is the mandatory deployment runway. Source projects may own
local development, tests, and image publishing, but they must not define or
execute their own operational Contabo/VPS compose, nginx, TLS, public-port,
rollback, or release path unless the user explicitly asks to replace the
Fortress runway in the same thread.

