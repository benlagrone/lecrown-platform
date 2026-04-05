# Site API Reference

This document is the concrete HTTP reference for other sites integrating with `lecrown-platform`.

It reflects the code that exists now.

## Base URLs

Local development:

- `http://localhost:8000`

Target production API hostname:

- `https://api.lecrowndevelopment.com`

Current intake position:

- the generalized cross-business intake endpoint now exists at `POST /intake/lead`
- the older `/inquiry` endpoint remains `properties`-only

## Health Check

### `GET /healthz`

Response:

```json
{
  "status": "ok"
}
```

Use this for basic connectivity checks before wiring a site integration.

## Authentication

Current implementation:

- `POST /auth/login`
- `GET /auth/me`

Current reality:

- this is a temporary local-admin auth flow
- the main content, inquiry, and distribution routes are not yet fully protected
- production auth is expected to move to `Keycloak`

Do not build long-lived third-party site integrations that depend on the current auth behavior staying exactly the same.

## Intake API

Use this for cross-business site lead capture when `lecrown-platform` should act as the intake hub.

Current first target:

- `AskMortgageAuthority`

### `POST /intake/lead`

Authentication:

- send header `X-Intake-Key` when `INTAKE_API_KEY` is configured on the platform

Request:

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
    "firstName": "Jordan",
    "lastName": "Smith",
    "emailAddress": "jordan@example.com",
    "phoneNumber": "713-555-0199",
    "description": "Looking to get pre-qualified.",
    "source": "Website"
  }
}
```

Response:

```json
{
  "submission_id": "uuid",
  "status": "processed",
  "delivery_target": "espocrm",
  "delivery_status": "delivered",
  "delivery_record_id": "crm-record-id",
  "source_site": "askmortgageauthority.com",
  "business_context": "AskMortgageAuthority",
  "product_context": "Mortgage",
  "created_at": "2026-04-01T00:00:00Z"
}
```

Current behavior:

- persists the raw inbound payload
- stores a normalized internal payload
- maps the submission into an `EspoCRM` lead payload
- attempts immediate downstream CRM delivery
- stores CRM response metadata whether delivery succeeds or fails

### `GET /intake/list`

Current access:

- admin bearer token required through the existing `POST /auth/login` flow

Purpose:

- inspect recent intake submissions
- filter by `source_site`

Example:

```bash
curl "http://localhost:8000/intake/list?source_site=askmortgageauthority.com" \
  -H "Authorization: Bearer <token>"
```

### `POST /auth/login`

Request:

```json
{
  "username": "admin",
  "password": "admin123"
}
```

Response:

```json
{
  "access_token": "token-value",
  "token_type": "bearer"
}
```

## Content API

Use this when a site or internal tool needs to create canonical content inside the platform.

### `POST /content/create`

Request:

```json
{
  "tenant": "development",
  "type": "insight",
  "title": "Why warehouse operations break down",
  "body": "Communication failures create delays and cost leakage.",
  "tags": ["operations", "industrial"],
  "publish_linkedin": true,
  "publish_site": true,
  "distribution": {
    "linkedin": true,
    "youtube": false,
    "website": true,
    "twitter": false
  },
  "media": {
    "video_generated": false,
    "video_path": null,
    "video_url": null,
    "render_status": null,
    "render_job_id": null,
    "youtube_video_id": null,
    "youtube_status": null
  }
}
```

Notes:

- `tenant` must be `development` or `properties`
- `type`, `title`, and `body` are required
- `distribution` is optional, but if supplied it should follow the shape above
- `media` defaults cleanly if omitted

Response shape:

```json
{
  "id": "uuid",
  "tenant": "development",
  "type": "insight",
  "title": "Why warehouse operations break down",
  "body": "Communication failures create delays and cost leakage.",
  "tags": ["operations", "industrial"],
  "distribution": {
    "linkedin": true,
    "youtube": false,
    "website": true,
    "twitter": false
  },
  "media": {
    "video_generated": false,
    "video_path": null,
    "video_url": null,
    "render_status": null,
    "render_job_id": null,
    "youtube_video_id": null,
    "youtube_status": null
  },
  "publish_linkedin": true,
  "publish_site": true,
  "linkedin_post_id": null,
  "linkedin_status": "queued",
  "created_at": "2026-03-31T00:00:00Z",
  "updated_at": "2026-03-31T00:00:00Z"
}
```

### `GET /content/list?tenant=development|properties`

Example:

```bash
curl "http://localhost:8000/content/list?tenant=development"
```

Response:

- array of `ContentRead` records

## Inquiry API

Use this only for `LeCrown Properties` inquiry intake.

### `POST /inquiry/create`

Request:

```json
{
  "tenant": "properties",
  "asset_type": "warehouse",
  "location": "Houston, TX",
  "problem": "Vacancy and operating issues",
  "contact_name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "555-123-4567"
}
```

Important:

- the tenant is fixed to `properties`
- this is not a cross-business CRM intake endpoint

Response:

```json
{
  "id": "uuid",
  "tenant": "properties",
  "asset_type": "warehouse",
  "location": "Houston, TX",
  "problem": "Vacancy and operating issues",
  "contact_name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "555-123-4567",
  "created_at": "2026-03-31T00:00:00Z"
}
```

### `GET /inquiry/list`

Returns:

- array of property inquiries

This is an internal/admin-facing endpoint, not the main public integration target for other businesses.

## Intake Direction

The intended long-term public integration boundary for external sites is not `/inquiry`.

That boundary is now starting at:

- `POST /intake/lead`

Until the generalized intake model expands further, do not mistake `/inquiry` for the cross-business lead-ingestion API.

## Distribution API

Use this when the site or admin flow wants the platform to orchestrate publishing.

### `POST /distribution/publish`

Request:

```json
{
  "content_id": "123",
  "channels": ["linkedin", "youtube"],
  "youtube_video_path": "/videos/warehouse.mp4",
  "video_style": "corporate_clean",
  "youtube_privacy_status": "private"
}
```

Allowed channels:

- `linkedin`
- `youtube`
- `twitter`
- `website`

Current behavior:

- `linkedin` is implemented
- `youtube` is implemented
- `twitter` is still a stub
- `website` currently returns a placeholder result

Response shape:

```json
{
  "content_id": "123",
  "results": {
    "linkedin": {
      "status": "published"
    },
    "youtube": {
      "status": "published",
      "video_id": "abc123"
    }
  }
}
```

## Direct Channel Publish APIs

These exist when a caller wants to publish one channel directly instead of using the distribution controller.

### `POST /linkedin/publish`

Request:

```json
{
  "content_id": "123"
}
```

Response:

```json
{
  "status": "published",
  "content_id": "123",
  "linkedin": {
    "id": "urn:li:share:123"
  }
}
```

### `POST /youtube/publish`

Mode 1: publish from stored content:

```json
{
  "content_id": "123",
  "privacy_status": "private"
}
```

Mode 2: direct publish without `content_id`:

```json
{
  "tenant": "development",
  "title": "Why warehouse operations break down",
  "description": "A direct explanation of the failure pattern.",
  "video_path": "/videos/warehouse.mp4",
  "tags": ["operations", "warehouse"],
  "privacy_status": "private",
  "category_id": "22",
  "notify_subscribers": false,
  "embeddable": true,
  "contains_synthetic_media": true
}
```

Direct publish rules:

- if `content_id` is omitted, `tenant`, `title`, `description`, and a video source are required
- video source can be `video_path` or `video_url`

## Error Expectations

Expect these common error classes:

- `422` for request validation failures
- `404` when a referenced `content_id` is missing
- `400` or `500` for channel misconfiguration or upstream publish problems

For external site integrations, treat publish calls as server-to-server operations and log full error bodies for debugging.

## CRM Boundary

Do not use these APIs as a general CRM substitute.

If the site needs:

- cross-business lead intake
- contact management
- follow-up workflows
- opportunity tracking

use `EspoCRM` instead.

Live CRM hostname:

- [crm.lecrowndevelopment.com](https://crm.lecrowndevelopment.com)
