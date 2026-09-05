# Site Integration Overview

This document is for other sites that need to integrate with the shared `LeCrown` systems.

The important boundary is:

- `lecrown-platform` is the shared content, distribution, and site-intake layer.
- `EspoCRM` is the shared operational CRM.
- `MediaStudio` is the external media-generation stack.

Other sites should integrate over HTTP APIs, not by sharing code, folders, or databases.

## System Roles

### `lecrown-platform`

Use `lecrown-platform` when a site needs to:

- create or manage canonical content
- trigger distribution to channels such as `LinkedIn` or `YouTube`
- eventually send normalized site-form submissions into shared workflows

### `EspoCRM`

Use `EspoCRM` when the platform needs to:

- create or update operational leads
- manage contacts
- manage follow-ups
- work with opportunities or pipeline states
- persist CRM records after the platform routes inbound submissions

### `MediaStudio`

Use `MediaStudio` only for media-generation workflows such as:

- rendering video
- narration generation
- music generation

Public sites should usually not call `MediaStudio` directly. They should call `lecrown-platform`, and let it orchestrate media generation when needed.

## Current Integration Rule

Use the decision below:

### If the site needs content or publishing

Integrate with `lecrown-platform`.

Examples:

- create a canonical content record
- trigger `LinkedIn`
- trigger `YouTube`
- request multi-channel distribution

### If the site needs shared CRM or non-property lead intake

Integrate with `lecrown-platform`, and let `lecrown-platform` route to `EspoCRM`.

Examples:

- `AskMortgageAuthority`
- future businesses
- cross-business lead forms
- sales follow-up workflows

## Current Tenant Model

`lecrown-platform` currently supports:

- `development`

That means:

- `lecrowndevelopment.com` integrations should use `tenant=development`

Other businesses should not force themselves into the wrong tenant. If the business does not fit those two tenants, the platform needs a broader intake and destination model instead of forcing a tenant mismatch.

## Deployment

Deployment is managed by the workspace deployment capability. The source
migration into metroLecrown does not activate a production endpoint.

## Authentication Reality

Current backend reality:

- `lecrown-platform` exposes a temporary local admin auth flow at `POST /auth/login`
- the main content, inquiry, and distribution routes are not yet locked behind a production-ready auth system
- `Keycloak` is the expected production direction

So for other site teams:

- do not assume the current auth flow is the final contract
- coordinate before treating the current open routes as a stable public API

## Recommended Integration Paths

### `lecrowndevelopment.com`

Use `lecrown-platform` for:

- canonical content
- distribution control
- future website publishing integration

### `AskMortgageAuthority`

Use `lecrown-platform` as the intended intake boundary, with `EspoCRM` downstream.

Current first-integration position:

- `AskMortgageAuthority` is the first external integration target
- the site already has a WordPress MU plugin with a usable normalization seam
- that seam should be repointed to `lecrown-platform`
- `lecrown-platform` should own inbound lead capture and CRM delivery

## Related Docs

- [Site API Reference](/Users/benjaminlagrone/Documents/projects/metroLecrown/platform/docs/site-api-reference.md)
- [Site Integration Checklist](/Users/benjaminlagrone/Documents/projects/metroLecrown/platform/docs/site-integration-checklist.md)
- [AskMortgageAuthority Integration](/Users/benjaminlagrone/Documents/projects/metroLecrown/platform/docs/askmortgageauthority-integration.md)
- [Intake Architecture](/Users/benjaminlagrone/Documents/projects/metroLecrown/platform/docs/intake-architecture.md)
- [EspoCRM Strategy](/Users/benjaminlagrone/Documents/projects/metroLecrown/platform/docs/espocrm-strategy.md)
- [MediaStudio API Inventory](/Users/benjaminlagrone/Documents/projects/metroLecrown/platform/docs/mediastudio-apis.md)
