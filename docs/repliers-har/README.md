# Repliers / HAR Platform Handoff

This directory is the platform-owned entry point for adding licensed Houston
Association of REALTORS (HAR) VOW data to the LeCrown back office.

Start with [platform-handoff.md](./platform-handoff.md).

## Current evidence state

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

These labels are intentionally narrow. Licensing approval does not prove that a
runtime key works, that HAR is returned, or that the platform is production
ready.

## Initial product boundary

- authenticated LeCrown staff and agents only
- read-only listing search and deterministic lead review
- synthetic or schema-only fixtures before live validation
- provider credentials remain server-side
- source, license scope, and freshness stay visible
- no public listing portal, bulk export, automated outreach, or silent CRM writes

## Related source material

The original evidence and governance collection remains in the
`lecrownproperties.com` repository under `docs/repliers-har/`. That collection
is the supporting record for licensing evidence, provider-contract research,
data governance, and the future live-validation runbook. This directory owns
how those constraints are applied inside `lecrown-platform`.
