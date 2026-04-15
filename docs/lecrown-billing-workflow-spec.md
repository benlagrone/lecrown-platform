# LeCrown Billing Workflow Spec

Updated: April 14, 2026

## Decision

`lecrown-platform` should gain a protected `Billing` page inside the existing admin UI.

That page should let an authenticated operator:

- prepare an invoice inside `lecrown-platform`
- generate the invoice PDF on the platform backend
- download the produced PDF immediately
- create a Gmail draft with the PDF attached

The allowed draft mailboxes for the first implementation are:

- `benjaminlagrone@gmail.com`
- `benjamin@lecrownproperties.com`

`lecrownbilling` remains a useful reference during migration, but the platform billing flow should run as a normal FastAPI and React feature, not as a Google Apps Script runtime.

## Why

The current billing workflow is split across:

- a local PDF workflow in `lecrownbilling`
- an Apps Script web app for Gmail draft creation and ledger behavior

That creates an unnecessary boundary for an internal operator workflow that should live in the main protected platform surface.

Moving invoice creation into `lecrown-platform` keeps billing work:

- behind the same auth boundary as the rest of the admin UI
- closer to the rest of LeCrown operational tooling
- independent from Apps Script deployment for day-to-day use

## Goals

- add a `Billing` page behind platform auth
- preserve the existing LeCrown invoice defaults and company routing
- preserve the exact existing local invoice PDF template
- let the operator download the generated invoice PDF
- let the operator create a Gmail draft with the PDF attached
- keep draft creation mailbox-limited to the approved addresses above
- keep invoice creation operator-facing and non-public

## Non-Goals

- do not auto-send the invoice email in `v1`
- do not expose billing pages publicly
- do not depend on Apps Script, `HtmlService`, or `google.script.run`
- do not turn `lecrown-platform` into a full accounting system in `v1`
- do not build a complete accounts receivable ledger before the invoice workflow itself is stable

## Current Source Of Truth To Preserve

The platform billing feature should preserve the current business defaults from `lecrownbilling`.

The platform billing feature should also preserve the current local invoice rendering template from:

- `/Users/benjaminlagrone/Documents/projects/lecrownbilling/scripts/generate_invoice.py`
- `/Users/benjaminlagrone/Documents/projects/lecrownbilling/templates/lecrown_properties_corp.json`
- `/Users/benjaminlagrone/Documents/projects/lecrownbilling/templates/lecrown_development_corp.json`

This should be treated as the visual source of truth for the platform version.

Current company mapping:

- `lecrown_development`
  - company name: `LeCrown Development Corp`
  - invoice prefix: `LCB`
  - default draft mailbox: `benjaminlagrone@gmail.com`
  - default recipient: `vendors@revolutiontechnologies.com`
  - default memo: work performed through `LeCrown Development Corp`
- `lecrown_properties`
  - company name: `LeCrown Properties Corp`
  - invoice prefix: `LCP`
  - default draft mailbox: `benjamin@lecrownproperties.com`
  - default recipient: `kensington.obh@gmail.com`
  - default CC: `edm.kpg@gmail.com`
  - default memo: work performed through `LeCrown Properties Corp`

The platform implementation should preserve the current invoice naming and recipient defaults unless they are intentionally overridden in the new platform UI.

## User Experience

### Page Placement

Add a new `Billing` page to the admin frontend navigation.

This page should sit inside the same invite-only auth shell as the existing protected admin views.

### Access Model

The page should be behind platform auth from the first release.

Recommended first access rule:

- signed-in users can access the page shell
- invoice generation and Gmail draft creation should be admin-only initially

That keeps mailbox-linked actions conservative while the feature is new.

### Main Form Areas

The `Billing` page should expose:

- company selector
- sender mailbox selector
- recipient email
- CC email
- bill-to name
- bill-to phone
- bill-to address
- issue date
- due date
- memo
- optional pay-online label and URL
- invoice number override
- invoice composition fields

### Invoice Composition Modes

The page should support two invoice composition modes.

#### 1. Time-entry mode

This mode preserves the current two-week LeCrown development workflow.

Fields:

- hourly rate
- week 1 ending date
- week 1 hours
- week 2 ending date
- week 2 hours

Behavior:

- the platform calculates line item amounts automatically
- the UI shows subtotal, total, and amount due previews
- this is the default mode for `LeCrown Development Corp`

#### 2. Custom line-item mode

This mode supports invoices like the existing `LeCrown Properties` examples.

Fields:

- one or more custom line items
- description
- optional quantity
- optional unit price
- amount

Behavior:

- the operator can add and remove rows
- the platform computes subtotal, total, and amount due
- this is the default mode for `LeCrown Properties Corp`

### Primary Actions

The page should expose:

- `Create Draft + Download PDF`
- `Download PDF Only`

Recommended behavior:

- `Create Draft + Download PDF` generates the invoice, stores enough metadata for audit, creates the Gmail draft with the PDF attached, and then downloads the PDF in the browser
- `Download PDF Only` generates the same PDF without touching Gmail

### Success State

After a successful draft creation, the page should show:

- invoice number
- PDF filename
- mailbox used
- recipient email
- CC email when present
- Gmail draft identifier
- a clear confirmation that the invoice was drafted and not sent

## Backend Shape

The billing workflow should be implemented as a normal FastAPI feature inside `lecrown-platform`.

Recommended backend slices:

- `backend/app/routes/invoice.py`
- `backend/app/services/invoice_service.py`
- `backend/app/schemas/invoice.py`

The existing PDF rendering logic in `lecrownbilling/scripts/generate_invoice.py` should be ported into a platform service instead of being shell-called across repos at runtime.

## PDF Generation

The platform should use a server-side PDF generator based on the current local LeCrown invoice renderer.

Preferred implementation:

- keep the exact current local invoice layout from `lecrownbilling`
- preserve company accent color, sender block, amount due card, memo section, and totals section
- return binary PDF bytes for direct browser download
- also persist the generated file long enough to support draft-creation and operator download confirmation

Important template rule:

- do not redesign the invoice
- do not create a platform-specific approximation
- do not switch to the older Apps Script Google Docs layout if it differs from the current local PDF output
- port or reuse the current local renderer so the platform PDF matches the local PDF template

Acceptance rule for implementation:

- for the same template JSON and invoice payload, the platform-generated PDF should match the current local `lecrownbilling` PDF structure, styling, and content ordering
- minor binary differences such as embedded metadata timestamps are acceptable
- visual layout drift is not acceptable

The platform should not require Google Docs or Apps Script to render invoices.

## Gmail Draft Creation

Gmail draft creation should be server-side.

Do not use a browser `mailto:` link for this workflow because:

- `mailto:` cannot reliably attach the generated PDF
- the operator needs a real Gmail draft with the invoice already attached

Recommended implementation:

- use the Gmail API
- use the `gmail.compose` scope
- create the draft in the selected mailbox using that mailbox's own OAuth refresh token
- upload a MIME message with the PDF attached

Important mailbox rule:

- when the operator selects `benjaminlagrone@gmail.com`, the platform should create the draft in that Gmail account
- when the operator selects `benjamin@lecrownproperties.com`, the platform should create the draft in that Gmail account
- the platform should not attempt to spoof one mailbox from the other mailbox's token

## Gmail Draft Content

The draft should preserve the current message pattern from the Apps Script version.

Subject:

- `New invoice from <company> #<invoiceNumber>`

Body should include:

- greeting
- invoice number
- company name
- memo or description
- invoice total
- due date
- optional pay-online line when configured
- closing with `Benjamin LaGrone`

The PDF should be attached to the draft.

## Invoice Numbering

The platform should support:

- auto-generated invoice numbers
- optional manual invoice number override

Recommended first numbering rule:

- `LCB-<year>-<sequence>` for `LeCrown Development Corp`
- `LCP-<year>-<sequence>` for `LeCrown Properties Corp`

Recommended first persistence shape:

- one per-company sequence record
- one invoice audit record for each generated invoice or draft

This avoids depending on Apps Script properties or a Google Sheet counter.

## Recommended Persistence

`v1` should keep persistence narrow but useful.

Recommended records:

- invoice sequence by company and year
- generated invoice record
- draft metadata when a Gmail draft is created

Suggested invoice audit fields:

- created at
- created by platform user
- company key
- company name
- invoice number
- invoice number override when used
- sender mailbox
- recipient email
- CC email
- issue date
- due date
- amount due
- currency
- Gmail draft id when applicable
- output filename

## Security Requirements

- keep the page behind existing platform auth
- keep Gmail OAuth credentials server-side only
- do not expose refresh tokens to the frontend
- restrict sender mailbox choices to an explicit allowlist
- do not allow arbitrary `From` addresses
- keep generated files in a controlled server directory
- avoid logging PDF contents or OAuth secrets

## Environment And Credential Requirements

The implementation will need server-side Google OAuth configuration.

Recommended required config:

- Google OAuth client id
- Google OAuth client secret
- refresh token for `benjaminlagrone@gmail.com`
- refresh token for `benjamin@lecrownproperties.com`
- invoice output directory path

Exact env var names can be finalized during implementation, but the design assumption is:

- one backend OAuth client
- one refresh token per supported mailbox

## Proposed API Contract

Recommended first endpoints:

- `GET /invoice/defaults?company_key=...`
- `POST /invoice/render`
- `POST /invoice/draft`

Suggested behaviors:

- `GET /invoice/defaults`
  - returns company defaults, sender mailbox options, default recipient values, and default composition mode
- `POST /invoice/render`
  - validates the payload
  - generates the invoice PDF
  - returns a downloadable PDF response
- `POST /invoice/draft`
  - validates the payload
  - generates the invoice PDF
  - creates the Gmail draft with the PDF attached
  - returns draft metadata plus a download reference for the produced PDF

## Frontend Integration Notes

The admin frontend should:

- add a `Billing` nav item
- require the existing protected auth flow before page entry
- load company defaults from the backend
- keep a live invoice preview summary in the UI
- allow the operator to create a draft and download without leaving the platform

The frontend should not assemble Gmail MIME messages in the browser.

## Local And Platform Workflow Relationship

The existing `lecrownbilling` repo should remain usable for local invoice generation during migration.

Near-term rule:

- local repo remains a reference and fallback workflow
- `lecrown-platform` becomes the preferred protected UI for invoice creation once the new page ships

## Rollout

Recommended rollout sequence:

1. add the protected `Billing` page shell and backend invoice schemas
2. port the invoice PDF renderer into `lecrown-platform`
3. ship `Download PDF Only`
4. add Gmail API draft creation for the two approved mailboxes
5. add invoice numbering persistence and audit records if not already included in step 2

If Gmail OAuth credentials are not ready, the PDF-only path can ship first behind the same page without changing the overall UI contract.

## Open Questions

- should invited non-admin members be allowed to create drafts, or should billing stay admin-only for longer
- should invoice records be stored only for audit, or also exposed later as a searchable internal invoice history page
- should the platform preserve the exact current Apps Script invoice body text, or treat that as operator-editable draft copy in a later iteration
