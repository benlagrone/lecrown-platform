# Billing and Entitlements Strategy

Updated: April 12, 2026

## Decision

`lecrown-platform` should become the central billing and entitlements control plane for LeCrown applications that may add paywalls.

This should be implemented as a normal platform API and data model, not as an MCP-first runtime dependency.

## Why

Several different applications may add paid access over time.

If each app owns its own:

- Stripe customer records
- subscription lifecycle logic
- pricing catalog
- webhook handling
- entitlement rules
- customer portal routing

then billing logic will fragment quickly and create avoidable migration work.

A shared platform layer is the cleaner long-term boundary.

## What Not To Do

Do not treat MCP as the production paywall runtime.

MCP is still useful for:

- internal planning
- operator workflows
- admin or support tooling
- inspection of subscription state
- entitlement diagnostics
- rollout checklists

But app access decisions should not depend on an MCP server in the user request path.

## Platform Boundary

`lecrown-platform` should own:

- Stripe customers
- Stripe subscriptions
- Stripe webhook processing
- invoice and billing status synchronization
- customer portal session creation
- product and price catalog metadata
- shared account or organization records
- membership records
- app-level entitlement state
- audit history for billing and entitlement changes

Each product app should still own:

- its own route guards
- its own API authorization checks
- app-specific provisioning side effects
- app-specific downgrade behavior
- local caching or snapshotting of entitlement state for resilience

## Runtime Model

Preferred runtime shape:

1. a product app authenticates the user
2. the product app resolves the active account or organization
3. the product app asks `lecrown-platform` for account entitlements
4. the product app enforces access in its own backend and UI

That means the platform is the source of truth for billing state, but each app remains responsible for enforcement.

## Recommended Core Model

The first shared model should stay narrow:

- `accounts`
- `account_memberships`
- `billing_customers`
- `billing_subscriptions`
- `billing_webhook_events`
- `products`
- `prices`
- `entitlements`
- `account_entitlements`

Recommended first entitlement shape:

- one account can have many app entitlements
- each entitlement should be a stable machine key
- examples:
  - `explorer_access`
  - `mortgage_leads_access`
  - `properties_pro_access`

## Stripe Position

Use Stripe Billing with:

- hosted Checkout Sessions for subscription signup
- Customer Portal for self-service subscription management
- webhook-driven synchronization for subscription truth

Do not use frontend-only gating as the source of truth.

Do not use raw PaymentIntents to build subscription renewal logic manually.

## Guidance For Energy Data Explorer

`Energy Data Explorer` should integrate against the shared platform once this exists.

Its premium surfaces should be enforced as account-scoped entitlements, not as ad hoc per-user checks.

Near-term product guidance for that app:

- keep public marketing routes public
- gate private workspaces, watchlists, weekly briefs, exports, and future paid diligence flows
- tie premium records to an owning account or organization before shipping self-serve billing

## MCP Role

MCP should be treated as an internal architecture and operator layer, not the public enforcement layer.

Good MCP uses here:

- inspect current billing status for an account
- inspect webhook failures
- view entitlement mapping for an app
- create operator-facing rollout or migration checklists
- surface pricing and integration metadata to internal assistants

Bad MCP use here:

- deciding whether an end user can open a paid page in production
- acting as the only live entitlement check for application traffic

## Rollout Order

Recommended rollout order:

1. define the shared account model in `lecrown-platform`
2. add Stripe customer, subscription, and webhook tables
3. add platform endpoints for checkout, portal, and entitlement lookup
4. add one entitlement-backed integration in the first app
5. add app-local middleware and route guards against the platform entitlement API
6. expand to additional apps only after the first integration proves stable

## Scope Discipline

Do not overbuild a generic billing platform before the second real app integration exists.

The first platform version should solve:

- one shared account model
- one Stripe integration path
- one entitlement API contract
- one or two app integrations

Anything beyond that should wait for concrete demand.

## Working Rule

Use this rule across LeCrown applications:

- centralize billing truth in `lecrown-platform`
- centralize entitlement truth in `lecrown-platform`
- keep application authorization and user-request enforcement inside each app
- use MCP only as an internal support and planning layer around billing, not as the billing runtime itself
