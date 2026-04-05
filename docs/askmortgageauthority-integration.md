# AskMortgageAuthority Integration

`askmortgageauthority.com` is the first external integration target for the shared `LeCrown` systems.

This document is the concrete handoff for that integration.

## Current Architecture Decision

For `AskMortgageAuthority`, the target architecture should be:

```text
AskMortgageAuthority (WordPress forms)
  -> lecrown-platform
  -> EspoCRM
```

Not:

```text
AskMortgageAuthority
  -> EspoCRM directly
```

Why:

- `lecrown-platform` should be the central integration layer
- `AskMortgageAuthority` is a mortgage business, not a `development|properties` tenant
- `EspoCRM` should remain a downstream operational system, not the public integration boundary

## What Already Exists

The local `AskMortgageAuthority` project exists at:

- [/Users/benjaminlagrone/Documents/projects/real-estate/askmortgageauthority.com](/Users/benjaminlagrone/Documents/projects/real-estate/askmortgageauthority.com)

The site already includes a WordPress MU plugin that sends form submissions to `EspoCRM`:

- [/Users/benjaminlagrone/Documents/projects/real-estate/askmortgageauthority.com/data/wp-content/mu-plugins/ama-crm-form-sync.php](/Users/benjaminlagrone/Documents/projects/real-estate/askmortgageauthority.com/data/wp-content/mu-plugins/ama-crm-form-sync.php)

That matters because the normalization and submission seam already exists in the site itself.

The change is architectural:

- keep the plugin
- change its target from `EspoCRM` to `lecrown-platform`

## Current AMA Form Sync Flow

The MU plugin currently:

- hooks into `WPForms`
- hooks into `Forminator`
- normalizes form fields into a lead payload
- posts that payload to `EspoCRM` at `/api/v1/Lead`

The hook-based approach is still the correct shape.

What should change is the destination:

```text
current:
WordPress form -> MU plugin -> EspoCRM

target:
WordPress form -> MU plugin -> lecrown-platform -> EspoCRM
```

## Target Platform Request

The platform endpoint the AMA plugin should call is:

- `POST /intake/lead`

Recommended request shape:

```json
{
  "source_site": "askmortgageauthority.com",
  "source_type": "wordpress",
  "form_provider": "WPForms",
  "form_id": "12",
  "form_name": "pre_qualify",
  "external_entry_id": "481",
  "page_url": "https://askmortgageauthority.com/get-pre-qualified/",
  "campaign": "spring-search",
  "business_context": "AskMortgageAuthority",
  "product_context": "Mortgage",
  "metadata": {
    "provider": "WPForms"
  },
  "lead": {
    "firstName": "Jane",
    "lastName": "Doe",
    "emailAddress": "jane@example.com",
    "phoneNumber": "5551234567",
    "description": "Imported from Forminator form #12",
    "source": "Website",
    "businessUnit": "AskMortgageAuthority",
    "productType": "Mortgage"
  }
}
```

If `INTAKE_API_KEY` is configured on the platform, the plugin should also send:

- header `X-Intake-Key`

## Lead Payload Shape

The AMA plugin builds an `EspoCRM` lead payload with these base fields:

```json
{
  "firstName": "Jane",
  "lastName": "Doe",
  "emailAddress": "jane@example.com",
  "phoneNumber": "5551234567",
  "description": "Imported from Forminator form #12"
}
```

It can also attach configured business metadata fields:

```json
{
  "source": "Website",
  "businessUnit": "AskMortgageAuthority",
  "productType": "Mortgage"
}
```

Those keys map directly to the plugin’s configurable field names.

## AMA Plugin Configuration

The current plugin supports these environment or constant keys:

- `AMA_CRM_SYNC_ENABLED`
- `AMA_CRM_BASE_URL`
- `AMA_CRM_API_KEY`
- `AMA_CRM_USERNAME`
- `AMA_CRM_PASSWORD`
- `AMA_CRM_TIMEOUT`
- `AMA_CRM_LEAD_SOURCE`
- `AMA_CRM_LEAD_SOURCE_FIELD`
- `AMA_CRM_BUSINESS_UNIT`
- `AMA_CRM_BUSINESS_UNIT_FIELD`
- `AMA_CRM_PRODUCT_TYPE`
- `AMA_CRM_PRODUCT_TYPE_FIELD`
- `AMA_CRM_WPFORMS_IDS`
- `AMA_CRM_FORMINATOR_IDS`

Current defaults in the plugin imply this intended shape:

- lead source field: `source`
- business unit field: `businessUnit`
- product type field: `productType`

## Recommended AMA Production Config

For the current direct-to-CRM plugin, the config looks like this:

```dotenv
AMA_CRM_SYNC_ENABLED=true
AMA_CRM_BASE_URL=https://crm.lecrowndevelopment.com
AMA_CRM_API_KEY=YOUR_ESPOCRM_API_KEY
AMA_CRM_LEAD_SOURCE=Website
AMA_CRM_LEAD_SOURCE_FIELD=source
AMA_CRM_BUSINESS_UNIT=AskMortgageAuthority
AMA_CRM_BUSINESS_UNIT_FIELD=businessUnit
AMA_CRM_PRODUCT_TYPE=Mortgage
AMA_CRM_PRODUCT_TYPE_FIELD=productType
```

Prefer API key auth over username/password if the plugin is still targeting CRM directly during transition.

For the long-term platform-first model, this config should eventually be replaced by platform-targeting values instead of CRM-targeting values.

## Form Coverage

The plugin is built to support:

- all `WPForms` submissions, unless restricted by `AMA_CRM_WPFORMS_IDS`
- all `Forminator` submissions, unless restricted by `AMA_CRM_FORMINATOR_IDS`

Recommended rollout:

1. restrict the sync to one known intake form first
2. verify lead creation in `EspoCRM`
3. then expand allowed form IDs

## Field Mapping Reality

The AMA plugin currently normalizes these user-facing form concepts:

- email
- phone
- first name
- last name
- full name
- notes or message

That means it is already suitable for:

- contact requests
- pre-qualification forms
- general lead capture

If a form needs mortgage-specific structured data later, the correct next move is to extend the plugin payload intentionally, not overload the current `lecrown-platform /inquiry` model.

## Where `lecrown-platform` Fits for AMA

### Phase 1

`AskMortgageAuthority` should move to `lecrown-platform` as the inbound lead-capture boundary.

That first platform feature now exists as:

- `POST /intake/lead`

### Phase 2

After intake lands in the platform, `lecrown-platform` should:

- normalize AMA form payloads
- preserve site and form attribution
- deliver to `EspoCRM`
- expose delivery status and retries

### Phase 3

`AskMortgageAuthority` can also use `lecrown-platform` for:

- canonical content creation
- multi-channel publishing
- future cross-site publishing workflows

## What Not To Do

- do not force `AskMortgageAuthority` into `tenant=development`
- do not reuse the current `properties` inquiry endpoint
- do not bypass `lecrown-platform` as the long-term intake boundary
- do not make public sites depend directly on CRM contracts forever

## First AMA Integration Milestone

1. Keep the AMA MU plugin, but retarget it to the platform instead of CRM
2. Submit one test AMA form into `POST /intake/lead`
3. Confirm the platform records attribution and delivers the mapped lead to `EspoCRM`
4. Verify the submission through `GET /intake/list`
5. Expand to the remaining AMA forms

## Follow-On Platform Milestone

After lead intake is stable, the next `AskMortgageAuthority` integration into `lecrown-platform` should continue expanding platform ownership, while keeping CRM downstream.

That means:

- publish canonical mortgage content through `lecrown-platform`
- distribute to `LinkedIn`, `YouTube`, and later site/blog channels
- keep CRM and publishing responsibilities separate
