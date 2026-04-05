# Site Integration Checklist

Use this checklist before wiring any other site into the shared `LeCrown` systems.

## 1. Choose the Correct Target

Use `lecrown-platform` if the site needs:

- content creation
- distribution control
- `LeCrown Properties` inquiries
- shared lead capture
- normalized site-form intake
- routing into shared downstream systems

Use `EspoCRM` if the workflow needs:

- CRM-side contact management
- pipeline workflows
- operational follow-up inside the CRM

For `AskMortgageAuthority`, the correct target path is:

- site -> `lecrown-platform` -> `EspoCRM`

Use `MediaStudio` only if you are intentionally building a media pipeline integration.

## 2. Confirm Business Context

For `lecrown-platform`, current valid tenants are:

- `development`
- `properties`

If the site does not fit one of those tenants cleanly, do not force it. Use the broader platform intake model rather than inventing a bad tenant fit.

## 3. Define the Integration Shape

For a site integration, decide:

- which system owns the workflow
- which endpoint is being called
- whether the call is browser-to-server or server-to-server
- what source attribution should be preserved

Recommended attribution fields even if the current endpoint does not store all of them yet:

- site hostname
- page URL
- campaign or ad source
- business context
- environment

## 4. Plan Authentication

Current `lecrown-platform` auth is temporary.

Before production integration, confirm:

- whether the integration will use a bearer token
- whether the site needs CORS access
- whether the call should go through a backend proxy instead of the browser

For `EspoCRM`, prefer API-user credentials or API keys when the platform calls it downstream.

## 5. Validate Environments

Keep per-environment base URLs explicit:

- local
- staging, if added later
- production

Do not hardcode `localhost` values into deployed sites.

## 6. Test the Smallest Working Flow

For `lecrown-platform`:

1. hit `GET /healthz`
2. send one valid request
3. inspect the returned record or publish response
4. confirm the side effect happened

For `EspoCRM`:

1. create one test lead
2. confirm it appears in the CRM UI
3. verify the business context fields are present

## 7. Document Ownership

Before launch, record:

- owning site
- owning team or operator
- destination system
- API endpoint
- credentials owner
- rollback path

## Reference Docs

- [Site Integration Overview](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/site-integration-overview.md)
- [Site API Reference](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/site-api-reference.md)
- [AskMortgageAuthority Integration](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/askmortgageauthority-integration.md)
- [Intake Architecture](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/intake-architecture.md)
- [EspoCRM Strategy](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/espocrm-strategy.md)
- [MediaStudio API Inventory](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/mediastudio-apis.md)
