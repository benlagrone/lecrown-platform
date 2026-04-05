# Feature Roadmap

`lecrown-platform` should evolve into the internet publishing focal point and site-capture hub for the business.

That means the platform should become the central place where teams:

- create and manage canonical content
- transform that content into channel-specific formats
- publish to blogs, `Twitter/X`, and other social platforms
- receive form submissions from different sites and landing pages
- normalize and funnel those submissions into the CRM
- manage multiple accounts per platform
- coordinate approvals, scheduling, and publishing history from one system

## Product Direction

The long-term goal is not just "post to one social network."

The long-term goal is:

- one content system
- one publishing control plane
- one intake layer for site forms
- many destinations
- many brand or operator accounts

This should support:

- company blogs and website content
- intake forms across multiple websites
- `Twitter/X`
- `LinkedIn`
- additional social platforms as needed
- multiple business identities, brands, or client accounts from one admin surface

## Roadmap Priorities

### 1. Blog and Website Publishing

Expand beyond placeholder website distribution into real publishing flows for:

- company blogs
- landing pages
- website news or updates
- CMS-backed sites such as WordPress or other API-driven website targets

Required capabilities:

- rich article publishing
- slug and metadata management
- draft vs publish states
- image and media attachment support
- per-site destination settings

### 2. Multi-Account Social Publishing

Make multi-account publishing a first-class capability.

The platform should support:

- multiple `Twitter/X` accounts
- multiple `LinkedIn` pages or profiles
- additional platform accounts over time
- account selection at publish time
- default account routing by tenant, brand, or content type

This is important because the platform should act as the publishing hub across more than one business identity, not a single-account tool.

### 3. Multi-Site Form Capture and CRM Funnel

The platform should also become the intake point for forms across different sites, landing pages, and campaign pages.

That means:

- forms from multiple websites should post into `lecrown-platform`
- submissions should be normalized into a shared internal intake shape
- the platform should route those submissions into the CRM over API boundaries
- site, page, campaign, and business context should be preserved with each submission

Required capabilities:

- per-site and per-form endpoint configuration
- field mapping from site forms into CRM-ready payloads
- spam or abuse protection hooks
- attribution fields such as source site, page, campaign, and tenant
- delivery status, retry handling, and audit history for CRM sync

This keeps public form capture centralized without turning `lecrown-platform` into the long-term CRM itself.

### 4. Channel Expansion

Current implemented or partial distribution support should expand into a broader publishing matrix:

- blogs and websites
- `Twitter/X`
- `LinkedIn`
- `YouTube`
- other social sites where the business chooses to maintain a presence

Each channel should keep its own:

- payload transformer
- account credentials
- destination configuration
- publish status
- audit history

### 5. Publishing Operations

To become the publishing focal point, the platform should also add:

- scheduled publishing
- approval workflows
- retries and failure visibility
- per-channel previews
- draft, queued, published, and failed states
- reusable campaign or cross-post workflows

### 6. Account and Destination Model

The current tenant model is a start, but the roadmap should move toward a more explicit destination model that can represent:

- tenant
- brand
- platform
- account
- site or page destination
- form endpoint
- CRM target

This makes it easier to publish the same source content across multiple accounts without hard-coding one destination per tenant.

## Near-Term Feature Sequence

1. Replace placeholder website publishing with a real blog or CMS publishing integration.
2. Upgrade `Twitter/X` from stub status to a real publisher.
3. Introduce a stored destination and intake model instead of assuming one account or one form path per tenant.
4. Add site form endpoints and mapping rules that funnel submissions into the CRM.
5. Add admin controls for selecting which account, page, blog, or site receives a post.
6. Add scheduling, queue visibility, and publish history across all destinations and CRM deliveries.

## Working Definition

The roadmap position should be understood as:

- `lecrown-platform` is becoming the central internet publishing system
- `lecrown-platform` should also be the intake layer for forms across multiple sites
- blog publishing is a core target, not a side feature
- social publishing should span more than one platform
- multi-account support is a core requirement, not a later edge case
- CRM funneling should happen through stable API integration, not by rebuilding the CRM in this repo
