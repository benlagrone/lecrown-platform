# Intake Architecture

`lecrown-platform` should be the central integration point for inbound site data.

That means public sites should not post directly to `EspoCRM` as the long-term architecture.

The correct shape is:

```text
website or app
  -> lecrown-platform
  -> normalization / attribution / validation
  -> downstream delivery
  -> EspoCRM
```

## Why This Matters

If sites post directly to `EspoCRM`:

- field mapping logic gets duplicated across sites
- attribution becomes inconsistent
- retry behavior becomes fragmented
- audit visibility is split across multiple systems
- replacing the CRM later becomes expensive

If sites post to `lecrown-platform` first:

- one integration boundary serves all sites
- one normalization layer controls payload shape
- one audit trail can track what came in and where it went
- `EspoCRM` remains replaceable as a downstream system
- the platform becomes the actual operating layer, not just a publisher

## Boundary

### `lecrown-platform` owns

- public or semi-public site intake endpoints
- source-site authentication
- field normalization
- attribution
- validation
- spam or abuse controls
- retry logic
- downstream routing
- delivery status
- intake audit history

### `EspoCRM` owns

- operational CRM records
- contact history
- pipeline and follow-up workflows
- user-facing CRM operations

## Recommended Flow

For cross-business lead capture:

```text
site form
  -> POST /intake/lead
  -> store inbound submission
  -> map to CRM payload
  -> send to EspoCRM
  -> store sync result
```

For tenant-specific property intake:

```text
site form
  -> POST /intake/lead
  -> map to properties inquiry flow and CRM delivery as needed
```

This avoids using the current `/inquiry` route as the long-term public integration boundary.

## Minimum Intake Payload Direction

The platform should move toward a generalized payload shape like:

```json
{
  "source_site": "askmortgageauthority.com",
  "source_type": "wordpress",
  "form_name": "pre_qualify",
  "business_context": "AskMortgageAuthority",
  "product_context": "Mortgage",
  "page_url": "https://askmortgageauthority.com/get-pre-qualified/",
  "submitted_at": "2026-04-01T12:00:00Z",
  "contact": {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@example.com",
    "phone": "5551234567"
  },
  "message": "Looking to get pre-qualified.",
  "metadata": {
    "provider": "WPForms",
    "form_id": 12,
    "campaign": "spring-search"
  }
}
```

The first stable step of this direction is now implemented at:

- `POST /intake/lead`

## Delivery Model

The platform should not assume only one downstream system.

An intake submission may need to route to:

- `EspoCRM`
- internal admin views
- analytics pipelines
- future automation or notification systems

That is another reason public sites should integrate with `lecrown-platform`, not CRM directly.

## AMA Implication

For `AskMortgageAuthority`, the strategic direction is:

```text
AskMortgageAuthority
  -> lecrown-platform
  -> EspoCRM
```

The existing WordPress MU plugin is still useful, and it can now be repointed to `lecrown-platform` instead of `EspoCRM` directly.

## First Implementation Step

The first concrete platform feature implied by this architecture is now in place:

- a generalized intake endpoint for external sites

Recommended first endpoint name:

- `POST /intake/lead`

Recommended first downstream target:

- `EspoCRM`

## Related Docs

- [AskMortgageAuthority Integration](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/askmortgageauthority-integration.md)
- [Site Integration Overview](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/site-integration-overview.md)
- [EspoCRM Strategy](/Users/benjaminlagrone/Documents/projects/real-estate/lecrown-platform/docs/espocrm-strategy.md)
