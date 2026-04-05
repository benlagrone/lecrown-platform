# EspoCRM Strategy

`EspoCRM` should be treated as a shared operational CRM that can support multiple businesses from one instance.

For `lecrown-platform`, the important architectural position is:

- `lecrown-platform` owns tenant-aware content, transformation, distribution, and site-facing business logic.
- `EspoCRM` owns operational CRM records, contact history, follow-ups, and opportunity tracking.
- Integration should happen over API boundaries.
- We should not expand the current in-app inquiry model into a full CRM before real operational usage is known.

## Current Position

The goal is not "a separate CRM per business."

The goal is:

- one CRM instance
- one database
- multiple business contexts

This supports:

- `LeCrown Properties`
- `AskMortgageAuthority`
- future businesses

without fragmenting contacts, lead history, and dashboards across multiple systems.

## Local Development Baseline

Fastest local path:

```yaml
version: "3.8"

services:
  espocrm:
    image: espocrm/espocrm
    container_name: espocrm
    ports:
      - "8080:80"
    environment:
      ESPOCRM_DATABASE_HOST: db
      ESPOCRM_DATABASE_USER: espocrm
      ESPOCRM_DATABASE_PASSWORD: espopass
      ESPOCRM_DATABASE_NAME: espocrm
    depends_on:
      - db

  db:
    image: mariadb:10.6
    container_name: espocrm-db
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: espocrm
      MYSQL_USER: espocrm
      MYSQL_PASSWORD: espopass
    volumes:
      - db_data:/var/lib/mysql

volumes:
  db_data:
```

Run:

```bash
docker compose up -d
```

Then complete the installer at:

- `http://localhost:8080`

## Core Data Model

Recommended entity direction:

### Leads

Primary intake entity.

Add custom fields:

- `business_unit`
  - `LeCrown Properties`
  - `AskMortgageAuthority`
  - `Other`
- `lead_source`
  - `Website`
  - `Calculator`
  - `Referral`
  - `Manual`
- `product_type`
  - `Mortgage`
  - `Property Management`
  - `Development`
  - `Other`
- `source_url`

### Accounts

Use for:

- client businesses
- partner companies
- optionally internal business entities if needed for reporting

### Contacts

Keep standard contact records, linked to accounts and business context as needed.

### Opportunities

Start with a simple shared pipeline:

- `New`
- `Contacted`
- `Qualified`
- `Converted`
- `Lost`

### Activities

Critical for follow-up operations.

Add fields:

- `next_follow_up_date`
- `priority`
- `business_unit`

## Multi-Business Separation

Do not create separate CRM instances or databases.

Use:

- business context fields
- saved filters
- dashboards
- teams when access control becomes necessary

### Start Simple

Initial recommendation:

- use a `business_unit` field
- create saved filters per business
- create dashboards per business

### Scale Cleanly

When needed, introduce EspoCRM Teams:

- `LeCrown`
- `Mortgage`
- `Development`

This gives cleaner access control without changing the database shape.

## Integration Position for LeCrown Platform

For now:

- keep `lecrown-platform` inquiry handling narrow
- treat `lecrown-platform` as the central intake and orchestration layer
- treat `EspoCRM` as the shared downstream operational system
- integrate through APIs instead of rebuilding full CRM logic inside this repo

That means the current `/inquiry` capability in `lecrown-platform` should be understood as:

- a tenant-specific intake surface
- not the long-term cross-business CRM model

## Immediate Integration Paths

### WordPress

Near-term:

- public forms should post into `lecrown-platform`
- `lecrown-platform` should normalize payloads and then deliver them to `EspoCRM`

Current CRM target downstream:

- `POST /api/v1/Lead`

Example shape:

```json
{
  "firstName": "John",
  "lastName": "Doe",
  "emailAddress": "john@email.com",
  "phoneNumber": "1234567890",
  "businessUnit": "Mortgage",
  "leadSource": "Website",
  "productType": "Mortgage"
}
```

Authentication:

- use `lecrown-platform` credentials at the site boundary
- use EspoCRM API users and API keys between `lecrown-platform` and `EspoCRM`

### LeCrown Platform

Near-term stance:

- do not make `lecrown-platform` the source of truth for CRM workflows
- if needed, sync selected inquiries or leads into `EspoCRM`
- keep the integration external and replaceable

## What Not To Do

- do not customize EspoCRM core files
- do not model every business perfectly upfront
- do not build complex workflow automation before real usage patterns emerge
- do not turn the current `inquiry` model into a fake full CRM
- do not make public sites depend directly on CRM contracts if the platform is meant to be central

## 7-Day Operational Goal

1. Run EspoCRM locally.
2. Add `business_unit` and `product_type` fields to leads.
3. Connect one real intake path.
4. Create one dashboard for new leads and follow-ups due.

## Long-Term Direction

`EspoCRM` is the operational baseline, not the final custom system.

Expected long-term shape:

- custom backend logic in `lecrown-platform` or a future Laravel service
- custom frontend/admin surfaces where needed
- AI and automation layered on top of stable operational data

For now, the right move is to keep the CRM centralized, observable, and lightly integrated.
