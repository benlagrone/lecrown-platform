# metroLecrown — Development and Government Contracting

This is the canonical workspace for LeCrown Development and government contracting.
The GitHub repository is `benlagrone/lecrown-platform`. Application code lives in
`platform/`; certification records and the browser tracker live in `data/` and
`tracker/`. LeCrown Properties and its brokerage workflows remain a separate project.

## Run and Validate

From this repository root:

```bash
./scripts/platform.sh setup       # Install backend and frontend dependencies
./scripts/platform.sh backend     # API: http://127.0.0.1:8000
./scripts/platform.sh frontend    # Admin: http://127.0.0.1:3000 (another terminal)
./scripts/serve-cert-tracker.sh    # Tracker: http://127.0.0.1:8765/tracker/
./scripts/platform.sh verify      # Backend tests, frontend build, tracker validation
```

Use Python 3.12 and Node.js 22.12 or newer. Local application setup starts with
a fresh Development database; it does not import the Properties database or
configure external CRM, Gmail, billing, or publishing credentials. See
[platform/README.md](platform/README.md) for application configuration.

Setup generates a unique local admin password and signing key in the ignored
`platform/.env` file. Use its `ADMIN_USERNAME` and `ADMIN_PASSWORD` to sign in.
Existing settings are preserved. No account is bootstrapped without a configured
password; Google Workspace authentication remains separately configurable.

The `publish-images.yml` workflow retained from upstream is a manually dispatched
compatibility bridge for `lecrown-properties-platform`, not a Development release
workflow. Deployment remains owned by the workspace deployment capability.

## Government Certification Portfolio Tracker

This project is the working folder for getting multiple companies ready to
pursue government contracts. The immediate goal is to move certifications from
informal intent into a tracked portfolio with companies, owners, dates,
evidence, and maintenance tasks.

## Start Here

1. Open [docs/certification-tracker.md](docs/certification-tracker.md).
2. Add every company to [data/companies.csv](data/companies.csv).
3. Add each company/certification pairing to
   [data/company-certifications.csv](data/company-certifications.csv).
4. Work the "This Week" checklist first.
5. Update the status table every time a portal task, document request, or
   agency response changes.
6. Track document storage and portal upload status in
   [data/document-portal-map.csv](data/document-portal-map.csv).
7. Keep sensitive credentials in `.local/`; do not move them into docs.

## Drawer Browser View

Open the browser-facing tracker from the project root:

```bash
./scripts/serve-cert-tracker.sh
```

Then open:

`http://127.0.0.1:8765/tracker/`

The drawer view reads the local CSV tracker files and does not submit external
portal registrations. The in-app drawer browser should use the loopback URL;
`tracker/data-snapshot.js` is a generated fallback for ordinary local browser
opens when CSV fetch is unavailable.

## Current Priority

The first serious lane for every company is federal readiness:

1. SAM.gov entity registration or renewal.
2. NAICS and capability profile cleanup.
3. MySBA Certifications account and eligibility questionnaire.
4. WOSB/EDWOSB and 8(a) decision based on ownership, control, and financial
   eligibility.
5. HUBZone eligibility check.

Local and state certifications remain tracked per company because they can
create near-term procurement opportunities while federal certifications move
through review.

## Working Files

- [docs/certification-tracker.md](docs/certification-tracker.md): operating
  tracker and certification checklists.
- [data/companies.csv](data/companies.csv): each company being prepared for
  certification.
- [data/company-certifications.csv](data/company-certifications.csv): one row
  per company per certification.
- [data/certification-activity.csv](data/certification-activity.csv): recent
  certification status changes, email-backed updates, and follow-up events.
- [data/certification-work-queue.csv](data/certification-work-queue.csv):
  dated operating queue for the next certification actions across companies,
  portals, documents, and buyer requirements.
- [data/company-intake.csv](data/company-intake.csv): required entity facts to
  collect before portal work.
- [data/evidence-register.csv](data/evidence-register.csv): document inventory
  by company, certification, and evidence type.
- [data/reusable-documents.csv](data/reusable-documents.csv): common documents
  that can be reused across certifications, vendor portals, and bids.
- [data/document-requirement-map.csv](data/document-requirement-map.csv): maps
  reusable documents to the certifications and buyers that usually request
  them.
- [data/document-storage-locations.csv](data/document-storage-locations.csv):
  approved storage locations, including the LeCrown document portal and private
  local storage.
- [data/document-portal-map.csv](data/document-portal-map.csv): maps each
  reusable document to its local path, source of truth, portal project ID, and
  portal document ID.
- [data/capability-statements.csv](data/capability-statements.csv): tracks
  master and buyer-specific capability statement drafts.
- [data/buyers.csv](data/buyers.csv): agencies, universities, and buying
  entities from the opportunity list.
- [data/buyer-certification-requirements.csv](data/buyer-certification-requirements.csv):
  buyer-specific registrations, certifications, portals, and compliance gates.
- [data/vendor-registration-packets.csv](data/vendor-registration-packets.csv):
  per-buyer registration packets showing how reusable evidence, including the
  METRO SBE certificate, should be used before submitting portal changes.
- [data/vendor-registration-execution-log.csv](data/vendor-registration-execution-log.csv):
  non-interactive registration route checks, blocked-submission reasons, and
  next actions for each packet.
- [data/certification-steps.csv](data/certification-steps.csv): spreadsheet-
  friendly reusable task list.
- [tracker/index.html](tracker/index.html): drawer-browser view over the CSV
  tracker data.
- [tracker/data-snapshot.js](tracker/data-snapshot.js): generated fallback
  snapshot used when the HTML page cannot fetch CSV files directly.
- [scripts/serve-cert-tracker.sh](scripts/serve-cert-tracker.sh): local server
  helper for opening the tracker in Codex or a browser.
- [docs/capability-statements/](docs/capability-statements/): capability
  statement drafts and templates.
- `output/pdf/`: completed/generated certification support PDFs.
- `tmp/pdfs/`: working PDF split/fill scripts and rendered pages.

## Document Portal Connection

The document portal target is the LeCrown client portal:

- Portal login: `https://lecrowndevelopment.com/portal/login`
- Portal API owner: `lecrowndevelopment-lead-api`
- Upload route: `POST /v1/portal/projects/:projectId/documents`

Track uploads in `data/document-portal-map.csv`. Do not paste public document
URLs into the tracker. Store portal project IDs, portal document IDs, Drive file
IDs if returned by the portal, and local source paths.

The intended portal project ID for this tracker is
`metro-lecrown-certification-tracker`.

Operational portal package ownership belongs to Fortress Phronesis:

`/Users/benjaminlagrone/Documents/projects/pericopeai.com/fortress-phronesis/ops/lecrown-portal/metro-lecrown-certification-tracker`

## Existing Document Inventory

- `Affidavit_of_Certification.pdf`
- `Personal Net Worth Statement 4.9.2024 (revised).pdf`
- `Updated_PNW_Form.pdf`
- `output/pdf/Affidavit_of_Certification_Jie_Huang_President.pdf`
- `output/pdf/PNW_Benjamin_LaGrone_FINAL.pdf`
- `output/pdf/PNW_Jie_Huang_FINAL.pdf`
