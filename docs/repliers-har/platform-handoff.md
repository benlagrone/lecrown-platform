# LeCrown Platform Repliers / HAR Handoff

## Objective

Add an agents-only property intelligence workspace to the LeCrown back office at
`backoffice.lecrownproperties.com`, backed by same-origin protected routes under
`backoffice.lecrownproperties.com/api/`. The separate API hostname may remain
available for approved system integrations, but the browser must use the
same-origin boundary.

The capability should help authorized LeCrown users search permitted HAR VOW
records, save structured searches, review explainable opportunity signals, and
see provenance and freshness. It is not a public IDX portal, a listing-entry
system, a contract or signature system, or an autonomous outreach tool.

## Evidence state

Repliers sent a `Full access granted for The Houston Association of REALTORS
(VOW) (standard)` notice for the standard API key. A later portal review still
showed `Sample Data MLS`, `VOW`, `ID: 110`, `Active`.

Use the following canonical state until new evidence is collected:

```text
Licensing: approved
Portal entitlement: sample-only
Provider key: not configured in this task
Local adapter: drafted in lecrownproperties.com, unvalidated
Deployment: not deployed by this task
Dataset observed: none
Last evidence: 2026-08-25 handoff based on Repliers approval email and portal review
Blocker: validate one bounded server-side response as HAR rather than Sample Data MLS
```

Do not represent the integration as operational, HAR-validated, deployed, or
production-validated until each state is separately proven.

## Ownership decision

`lecrown-platform` owns the authenticated back-office product and the durable
LeCrown API contract.

The existing uncommitted Repliers adapter observed in
`lecrownproperties.com/server.py` is reference material only. It remains owned
by its original task and must not be copied wholesale, executed, modified, or
treated as validated without explicit reconciliation.

The public `lecrownproperties.com` browser must not call Repliers directly and
must not receive provider credentials or unrestricted licensed payloads.

## Platform integration map

### Backend

Add a dedicated property-data module using the repository's existing FastAPI
structure:

```text
backend/app/routes/property_data.py
backend/app/schemas/property_data.py
backend/app/services/property_data_service.py
backend/app/services/repliers_client.py
backend/tests/test_property_data.py
backend/tests/fixtures/property_data/
```

Responsibilities:

- `property_data.py`: authenticated, bounded HTTP routes
- `property_data.py` schemas: structured filters and versioned response models
- `property_data_service.py`: field policy, saved-search behavior, lead rules,
  provenance, and audit coordination
- `repliers_client.py`: server-side provider authentication, timeouts, response
  limits, provider error translation, and source detection
- tests and fixtures: synthetic records and controlled mock-provider responses

Do not add the provider key to frontend environment variables, request URLs,
client bundles, logs, screenshots, or tracked fixtures.

### Authentication and authorization

Use the platform's existing authentication dependencies in
`backend/app/core/security.py`:

- `get_current_user` for permitted agent workflows
- `get_current_admin` for configuration, access review, and future entitlement
  diagnostics

Authentication alone must not imply bulk export, administrative access, or
permission to see every provider field. Add explicit role and field policy as
the integration matures.

The platform currently uses its own JWT-based admin authentication. Do not add
a second Keycloak dependency merely because the source-site prototype mentions
Keycloak. A future identity migration should be a separate platform decision.

### Frontend

Extend the existing React admin under `frontend/admin/src/` with a distinct
`Property intelligence` workspace. Keep the initial navigation inside the
authenticated admin shell.

Initial views:

1. Access status and provenance
2. Structured property search
3. Saved searches
4. Lead review queue
5. Listing detail with field-level source and freshness

Until live HAR validation succeeds, the workspace must show a prominent
`Synthetic preview` state and use only synthetic or schema-only fixtures.

### Shared client contract

Add typed request and response models to:

```text
frontend/shared/types.ts
frontend/shared/api.ts
```

The browser calls only the LeCrown API. It never constructs a Repliers request,
holds the provider key, or receives arbitrary upstream passthrough data.

## Proposed LeCrown API contract

The first stable namespace should be `/property-data`:

```text
GET  /property-data/status
GET  /property-data/search
GET  /property-data/searches
POST /property-data/searches
GET  /property-data/signals
PATCH /property-data/signals/{signal_id}
```

The initial status route must describe evidence, not expose secrets:

```json
{
  "contract_version": "1",
  "licensing": "approved",
  "portal_entitlement": "sample-only",
  "provider_key": "not_configured",
  "adapter": "not_implemented",
  "dataset_observed": "none",
  "mode": "synthetic_preview"
}
```

A future validated search response should use a LeCrown-owned envelope:

```json
{
  "contract_version": "1",
  "source": {
    "provider": "repliers",
    "dataset": "har-vow",
    "retrieved_at": "2026-08-25T00:00:00Z",
    "license_scope": "agents-only"
  },
  "query": {
    "page": 1,
    "results_per_page": 25
  },
  "pagination": {
    "page": 1,
    "num_pages": 1,
    "page_size": 25,
    "count": 0
  },
  "listings": []
}
```

The `har-vow` dataset label may be returned only after provider evidence proves
the response is HAR. Never relabel Sample Data MLS as HAR.

## Search policy

Use a validated structured filter model rather than arbitrary provider query
passthrough. Candidate filters include:

- city, area, location identifier, and bounded radius
- listing status and last status
- class and property type
- price, beds, baths, square footage, and acreage ranges
- list or provider update date
- image availability
- agent, office, and brokerage identifiers
- pagination and approved sort options

Actual status, class, property type, agent, office, and brokerage identifiers
must be learned from a validated HAR response. Do not hard-code names as stable
identifiers.

## Lead-review policy

Start with deterministic, explainable rules. Every signal must include:

- signal type and rule version
- listing identifier and source
- plain-language explanation
- supporting field/value facts
- generation and expiry timestamps
- data-completeness confidence
- review status, reviewer, and review timestamp

Allowed review states:

```text
new
reviewing
qualified
dismissed
expired
actioned
```

`qualified` does not mean contacted, converted, or represented. No rule may use
protected-class attributes, inferred protected characteristics, neighborhood
demographics, or proxy features for steering.

## CRM and outreach boundary

The initial property-data service is read-only.

Do not automatically:

- create or update an EspoCRM record
- change a pipeline stage
- send email or SMS
- place a call
- launch advertising
- claim agency or representation

Any later CRM action requires a visible destination, explicit user action,
minimal field mapping, duplicate detection, provenance, an audit event, and a
correction path. Outreach requires its own consent, suppression, sender,
template, and approval controls.

## Data governance

### Secrets

`REPLIERS_API_KEY` is server-side only. It must never be committed, displayed,
logged, returned to the browser, or included in URLs.

### Licensed records

Until the executed agreement is reviewed for retention:

- do not persist complete provider payloads by default
- do not mirror the listing photo library
- return live responses with `Cache-Control: no-store`
- save structured query definitions rather than result snapshots
- record only minimum audit metadata
- re-fetch current facts when needed

### Provenance

Every surfaced fact should retain provider, dataset, provider record ID, source
field, retrieval time, provider update time when available, license scope,
transformation or rule version, and conflict state.

Ancillary parcel, tax, appraisal, flood, solar, weather, environmental,
infrastructure, and GridScope facts remain separate sources with their own
licenses, freshness, and conflict behavior.

### Export

Bulk export is disabled by default. CSV or other export cannot be used to bypass
field policy or licensed-audience restrictions.

## Delivery sequence

### Phase 0: Handoff and ownership

- keep this document as the platform entry point
- preserve the source evidence collection in `lecrownproperties.com`
- reconcile the pre-existing adapter before reusing any implementation

Exit: ownership and starting state are explicit.

### Phase 1: Synthetic workspace

- add protected platform status route
- add typed synthetic fixtures
- build authenticated search, saved-search, provenance, and lead-review UI
- show `Synthetic preview` throughout
- add mock-backed tests only

Exit: the product workflow is reviewable without credentials or licensed data.

### Phase 2: Secure provider adapter

- implement a reviewed server-side client
- add query and response allowlists
- add timeout, pagination, and response-size limits
- add stable provider error translation
- add secret-free audit events

Exit: controlled mock tests pass and unauthorized calls fail locally.

### Phase 3: Bounded HAR validation

This phase requires Benjamin's explicit authorization in the active task.

- configure the key through the approved secret owner
- make one authenticated Houston request with one result
- capture only source identity, status, pagination, and top-level schema
- stop if the response is sample, ambiguous, oversized, or leaks sensitive data

Exit: `HAR response validated` or a documented failure/inconclusive result.

### Phase 4: Licensed internal search

- replace synthetic valid values with validated HAR values
- enforce field policy
- validate agent, office, and brokerage scopes
- keep source and freshness visible
- keep public access and bulk export disabled

Exit: authorized agents can review bounded, source-labelled HAR records.

### Phase 5: Lead intelligence and market support

- enable approved deterministic lead rules
- add aggregates and market summaries
- support human-reviewed CMA preparation
- preserve the distinction between analysis, appraisal, and legal conclusions

Exit: outputs are explainable, reviewable, and evidence-linked.

## Stop conditions

Stop immediately if:

- a secret appears in output, source control, browser code, or logs
- a response identifies Sample Data MLS
- dataset identity is ambiguous
- provider access is reachable without LeCrown authentication
- a public route exposes licensed data
- a test would create material quota, cost, or operational impact
- the executed agreement is unclear for the intended display or retention
- overlapping worktree changes cannot be reconciled safely

Credential changes, provider support messages, deployment, and production
validation each require separate authorization.

## First implementation acceptance criteria

- authenticated platform users can open the property-intelligence workspace
- all records are explicitly synthetic
- structured search and pagination operate against fixtures
- saved searches store definitions rather than provider results
- lead signals show rules and supporting facts
- no provider or internal service credential reaches the browser
- no public, CRM-write, outreach, or export behavior is enabled
- tests run without a live provider call
