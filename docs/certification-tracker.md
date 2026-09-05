# Government Certification Tracker

Last updated: 2026-08-22

## Operating Rule

Every company/certification pair must have one next action, one owner, one due
date, one evidence folder or document path, and one maintenance rule. If a
company/certification pair does not have a next action, it is not being worked.

Do not copy eligibility assumptions across companies. Ownership, control,
principal office, revenue, NAICS, employee residency, and disadvantaged-owner
facts must be verified separately for each company.

## Portfolio Files

- `data/companies.csv`: one row per company.
- `data/company-certifications.csv`: one row per company per certification.
- `data/certification-activity.csv`: one row per certification status change,
  email-backed update, document follow-up, or portal event.
- `data/certification-work-queue.csv`: one row per current operating task,
  prioritized across company, certification, document, portal, and buyer work.
- `data/company-intake.csv`: one row per required company fact.
- `data/evidence-register.csv`: one row per supporting document.
- `data/reusable-documents.csv`: common documents that should be collected once
  and reused across portals, certifications, and bids.
- `data/document-requirement-map.csv`: maps reusable documents to certification
  and buyer requirements.
- `data/document-storage-locations.csv`: approved document storage locations,
  including local private storage and the LeCrown document portal.
- `data/document-portal-map.csv`: one row per reusable document that needs to
  be found, created, uploaded, or linked in the portal.
- `data/capability-statements.csv`: one row per master or buyer-specific
  capability statement.
- `data/buyers.csv`: one row per target buyer or agency.
- `data/buyer-certification-requirements.csv`: one row per buyer-specific
  certification, registration, portal, or compliance gate.
- `data/vendor-registration-packets.csv`: one row per buyer/vendor portal route
  showing which reusable documents are ready for registration profiles and where
  submission must wait for review.
- `data/certification-steps.csv`: reusable steps that can be copied or filtered
  for each company/certification pair.

## Current Work Queue

Work the queue in `data/certification-work-queue.csv`. The top priority is
getting the City of Houston application into a signable state before the
2026-09-12 deletion date.

| Priority | Due | Workstream | Next Action | Definition of Done |
| --- | --- | --- | --- | --- |
| Critical | 2026-07-31 | COH document packet | Build the application `6369689` document packet inventory from the 13 mandatory attachments and mark each item found, missing, or private. | Every mandatory document has a tracker row with source of truth, storage status, owner, and upload decision. |
| Critical | 2026-07-31 | COH application sections | Complete the six incomplete B2Gnow form sections starting with Section 3 Ownership. | B2Gnow shows all required form sections complete before document upload and signature. |
| High | 2026-07-31 | Strategic Purchasing registration | Locate or create City of Houston Strategic Purchasing vendor/supplier registration proof. | Proof is saved or linked in the tracker and ready for B2Gnow upload. |
| High | 2026-08-24 | METRO certification proof | Sync the Google Drive METRO SBE certificate proof into the LeCrown document portal and record the portal document ID. | Portal document ID is recorded and renewal date `2029-07-15` is tracked. |
| High | 2026-08-02 | Document portal setup | Verify or create portal project `metro-lecrown-certification-tracker` before uploading sensitive records. | Portal project exists and `data/document-portal-map.csv` rows have project and first document IDs. |
| Medium | 2026-08-03 | Capability statement | Finish Metro LeCrown master capability statement and export the first one-page PDF. | Master PDF exists and is mapped for portal upload. |
| Medium | 2026-08-05 | SAM.gov | Log into SAM.gov and record entity registration status, UEI, CAGE if assigned, and renewal date. | Tracker contains current SAM status and renewal rule without sensitive bank or tax values. |
| Medium | 2026-08-07 | MySBA | Create or access MySBA Certifications and run WOSB, EDWOSB, 8(a), and HUBZone eligibility checks. | Questionnaire outcomes are recorded and one federal submission lane is selected. |
| Medium | 2026-08-07 | UH and UT readiness | Verify CMBL status and prepare UH and UT vendor profile data from the reusable document list. | CMBL status is known and UH/UT required profile documents are mapped. |
| Medium | 2026-08-09 | Company roster | Replace placeholder companies with legal entity details or mark them paused. | Every company is active with intake rows or intentionally paused with a reason. |

## Vendor Registration Packet Queue

The METRO SBE certificate is now registration evidence, not just a stored proof.
Use `data/vendor-registration-packets.csv` to stage buyer profile updates before
submitting any external portal changes.

Registration execution evidence is tracked in
`data/vendor-registration-execution-log.csv`. The 2026-08-23 non-interactive
pass checked every route without changing external portals. No registration was
submitted because the active blockers are authenticated portal sessions, route
validation, and missing private company intake fields in
`data/company-intake.csv`.

| Buyer Route | How The METRO SBE Certificate Is Used | Remaining Gate |
| --- | --- | --- |
| METRO SAP Ariba | Attach or list active SBE certification dates in the vendor profile. | Confirm account/profile access and NIGP codes before submitting. |
| METRO GovSpend | Use SBE status and commodity filters to improve small-purchase matching. | Verify account access and filter setup. |
| METRO SBE Business Assessment | Use active SBE proof in assessment answers and procurement guidance request. | Review capability statement and capacity answers before submission. |
| Harris County Bonfire | Use SBE proof where supplier profile or solicitations ask for certification evidence; use NIGP codes for opportunity notifications. Official purchasing source: `https://purchasing.harriscountytx.gov/`. | Stage Bonfire profile and submit only after reviewing company/contact/NIGP fields. |
| HCC Bonfire | Use SBE proof as supporting evidence where HCC recognizes the certifying organization or the profile requests certifications. | Stage Bonfire bidder profile, W-9/COI forms only when requested, and category selections. |
| Lone Star College | Use SBE proof only where supplier profile asks for certifications; the primary task is e-bid/iStar registration. | Verify bidder account, supplier account need, and commodity categories before entering payment data. |
| San Jacinto College | Use SBE proof only where the e-bidding profile or solicitation asks for certification evidence. | Stage e-bidding profile and category selections. |
| HISD IonWave | Use SBE proof only where IonWave asks for certification evidence. | Stage IonWave vendor profile and commodity code selections. |
| Spring Branch ISD | Use SBE proof as supporting certification evidence after the current registration route is verified. | Confirm whether SBISD currently uses VSS, Public Purchase, or Purchasing-assisted registration before submitting. |
| Katy ISD OpenGov/VSS | Use SBE proof in OpenGov only if certification fields exist; keep VSS payment docs separate. | Verify prior OpenGov account invitation, then stage W-9/Debarment/HB89/SB252 only for payment setup. |
| TEA Bonfire | Use SBE proof as supporting evidence only if profile or solicitation asks for certifications; NIGP codes drive notifications. | Verify Bonfire account/NIGP setup; no TEA response submission without approval. |
| TRS PAVES | Use SBE proof only if PAVES profile or solicitation asks for certification evidence. | Verify PAVES registration before working TRS000683 or later opportunities. |
| University of Houston | Keep SBE proof in the packet as supporting evidence. | Verify CMBL status; UH vendor setup is separate and may require tax/payment data only after request. |
| University of Texas at Austin | Use SBE proof where Bonfire or vendor profile asks for certification evidence. | Verify Bonfire profile and CMBL/VID/PIF route. |
| City of Houston | Use METRO SBE as related proof only; it does not replace City OBO requirements. | Complete Strategic Purchasing proof and City OBO application blockers. |
| TDCJ and Texas buyers | Use SBE proof in the buyer packet. | Verify CMBL status and solicitation route. |
| Federal prime subcontracting targets | Add SBE proof to supplier-diversity packets and outreach profiles for Accenture Federal, SAIC, CGI Federal, Booz Allen, Dell Federal, and KBR. | Tailor capability statement and validate Dell/KBR routes before submission or outreach. |

### Registration Execution Pass

| Date | Scope | Result | Blocking Gate |
| --- | --- | --- | --- |
| 2026-08-23 | All vendor registration packets | Routes checked and connected to `data/vendor-registration-execution-log.csv`; no external portal submission made. | Private intake profile, authenticated portal sessions, and Dell/KBR/TDCJ route validation. |

## 30-Day Push Plan Reset

| Window | Outcome | Definition of Done |
| --- | --- | --- |
| 2026-07-28 to 2026-07-31 | City of Houston application made signable | Six incomplete sections resolved and all 13 mandatory attachments classified as found, missing, private, or uploaded. |
| 2026-08-01 to 2026-08-03 | Document portal and METRO proof secured | Portal project exists, first document IDs are recorded, METRO proof is stored, and renewal tracking is in place. |
| 2026-08-04 to 2026-08-07 | Federal foundation verified | SAM.gov status, UEI/CAGE if assigned, MySBA access, and preliminary eligibility outcomes are recorded. |
| 2026-08-08 to 2026-08-14 | Buyer readiness packet built | Master capability statement PDF, CMBL status, UH/UT vendor data, and reusable document map are ready. |
| 2026-08-15 to 2026-08-21 | Multi-company portfolio cleaned up | Placeholder companies are either fully onboarded or explicitly paused with a reason and next review date. |

## Company Roster

| Company ID | Legal Name | Status | Primary Cert Owner | Immediate Need | Evidence Root |
| --- | --- | --- | --- | --- | --- |
| metro_lecrown | Metro LeCrown | Active | Benjamin | Work `certq-001` through `certq-005` first. | `output/pdf/` |
| company_2 | TBD | Placeholder | TBD | Add legal/entity details. | TBD |
| company_3 | TBD | Placeholder | TBD | Add legal/entity details. | TBD |

## Portfolio Status Dashboard

| Company | Certification | Why It Matters | Status | Current Gate | Next Action | Owner | Due | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Metro LeCrown | SAM.gov Entity Registration | Required to bid directly on federal contracts and apply for federal awards. | Not verified | Need active entity registration, UEI, and renewal date. | Work `certq-007`: log into SAM.gov and capture current entity status. | Benjamin | 2026-08-05 | TBD |
| Metro LeCrown | MySBA Certifications Account | Portal used for many SBA certification workflows and eligibility checks. | Not started | Need account access and questionnaires. | Work `certq-008`: create/login and run eligibility checks. | Benjamin | 2026-08-07 | TBD |
| Metro LeCrown | WOSB / EDWOSB | Federal set-asides for women-owned small businesses. | Candidate | Must verify ownership/control and financial eligibility. | Use MySBA results to decide whether WOSB or EDWOSB is the active lane. | Benjamin/Jie | 2026-08-07 | `output/pdf/PNW_Jie_Huang_FINAL.pdf` |
| Metro LeCrown | 8(a) Business Development | SBA business development program for socially and economically disadvantaged businesses. | Candidate | Must verify readiness and eligibility before submission. | Use MySBA results to decide whether 8(a) is ready or should wait. | Benjamin/Jie | 2026-08-07 | PNW files, tax/ownership docs |
| Metro LeCrown | HUBZone | Federal set-asides and price evaluation preference if office/workforce qualify. | Eligibility unknown | Principal office and 35% employee residency must be checked on the HUBZone map. | Use MySBA/HUBZone checks to classify eligible, not eligible, or needs data. | Benjamin | 2026-08-07 | Address list |
| Metro LeCrown | City of Houston OBO M/WBE or SBE | Local procurement and subcontracting opportunities. | In progress - application incomplete | B2Gnow portal verifies application `6369689` is incomplete at 52% for MBE/WBE/SBE/PDBE New Application. | Work `certq-001` through `certq-003` before signing or submitting. | Benjamin/Jie | 2026-07-31 | B2Gnow VID `20922339`, Gmail message `19f849397ab03b33` |
| Metro LeCrown | Houston METRO Certification | METRO vendor readiness, small-business certification, and procurement access. | Certified - Drive proof found | Active SBE certification effective 2026-07-15; renewal due 2029-07-15. Drive file `lecrownSBEMetro.pdf` was found on 2026-08-22. | Work `certq-004`: sync Google Drive proof into the document portal and record the portal document ID. | Benjamin/Jie | 2026-08-24 | B2Gnow VID `20922339`, Gmail message `19f848b56634c415`, Google Drive file ID `1vC1t1WJDdOjOKBfp6q_qN47MtQiOlcEi` |
| Metro LeCrown | Texas HUB | State procurement visibility and subcontracting opportunities. | Candidate | Need eligibility and application route confirmation. | Confirm whether Metro LeCrown meets Texas HUB criteria and start application packet. | Benjamin | TBD | TBD |
| Metro LeCrown | TxDOT DBE / ACDBE | Transportation contract opportunities if eligible. | Candidate | Need eligibility and target opportunity fit. | Decide whether transportation work is a real pursuit lane. | Benjamin | TBD | TBD |
| TBD Company 2 | SAM.gov Entity Registration | Required federal foundation. | Placeholder | Need legal/entity details. | Add company to roster and confirm SAM.gov status. | TBD | TBD | TBD |
| TBD Company 3 | SAM.gov Entity Registration | Required federal foundation. | Placeholder | Need legal/entity details. | Add company to roster and confirm SAM.gov status. | TBD | TBD | TBD |

## Recent Certification Activity

| Date | Company | Certification | Activity | Status | Source | Follow-up |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-07-21 | Metro LeCrown | Houston METRO Certification | LeCrown Development received METRO Certification; renewal date is 2029-07-15. | Recorded | Gmail message `19f848b56634c415` | Save certificate proof to the document portal. |
| 2026-07-21 | Metro LeCrown | City of Houston OBO M/WBE or SBE | City of Houston certification has been started. | Next action | Gmail message `19f848b56634c415` | Continue completing COH certification. |
| 2026-07-21 | Metro LeCrown | City of Houston OBO M/WBE or SBE | Jessica sent a separate request to complete COH certification. | Next action | Gmail message `19f849397ab03b33` | Keep portal credentials outside tracker files. |
| 2026-07-21 | Metro LeCrown | Houston METRO Certification | Certificate proof still needs to be saved to the document portal. | Next action | Certification tracker | Create or link portal document record. |
| 2026-07-22 | Metro LeCrown | City of Houston OBO M/WBE or SBE | COH certification login information received for the same portal URL as METRO but with a separate credential set. | Next action | Gmail message `19f849397ab03b33` | Store credentials only in `.local` and continue COH certification. |
| 2026-07-24 | Metro LeCrown | Houston METRO Certification | B2Gnow portal verifies active SBE certification effective 2026-07-15 and renewal due 2029-07-15. | Recorded | B2Gnow VID `20922339` | Save certificate proof to the document portal and add renewal alerts. |
| 2026-07-24 | Metro LeCrown | City of Houston OBO M/WBE or SBE | B2Gnow portal verifies application `6369689` is incomplete at 52%. | Next action | B2Gnow VID `20922339` | Fill in the COH application and identify missing required sections/documents. |
| 2026-07-24 | Metro LeCrown | City of Houston OBO M/WBE or SBE | B2Gnow document tab shows `0 attached of 13 mandatory; 0 attached of 13 required`. | Next action | B2Gnow CertAppID `1218660` | Prepare mandatory document packet before upload/sign/submit. |
| 2026-08-22 | Metro LeCrown | Houston METRO Certification | Recent private Google Drive upload `lecrownSBEMetro.pdf` found and recorded as METRO SBE certificate proof. | In progress | Google Drive file ID `1vC1t1WJDdOjOKBfp6q_qN47MtQiOlcEi` | Sync proof into the LeCrown document portal and record portal document ID. |
| 2026-08-22 | Metro LeCrown | Harris County Bonfire | Harris County Bonfire registration route added as a staged vendor opportunity packet. | Staged | Harris County Bonfire registration | Stage company profile, NIGP codes, and SBE proof before external submission. |
| 2026-08-22 | Metro LeCrown | Older Opportunity Tracker | Older local-buyer and prime-subcontractor targets were reconciled into staged registration packets. | Staged | `data/vendor-registration-packets.csv` | Open each portal one at a time and record confirmation IDs or auth-required blockers. |
| 2026-08-23 | Metro LeCrown | Vendor Registrations | Every packet received a non-interactive route check and was connected to an execution log. | Blocked | `data/vendor-registration-execution-log.csv` | Complete private company intake and authenticated portal sessions before submitting registrations. |

## City of Houston Application 6369689 Blockers

Portal status observed 2026-07-24:

- Application type: MBE/WBE/SBE/PDBE New Application.
- Status: Incomplete, 52% complete.
- Started: 2026-06-07.
- Date for deletion: 2026-09-12.
- Contact person: Jie Huang.
- Document status: 0 of 13 mandatory documents attached.

Incomplete form sections:

- Section 1: General Information - Business Profile: 9 of 10 required complete.
- Section 3: Ownership: 0 of 1 required complete.
- Section 4: Control - Officers & Board of Directors: 2 of 4 required complete.
- Section 4: Control - Inventory: 1 of 5 required complete.
- Section 4: Control - Licenses & Contracts: 1 of 3 required complete.
- Section 5: Additional Information: 4 of 5 required complete.

Mandatory document attachments shown as not attached:

- Current minutes of all stockholders and board of directors meetings.
- Signed and notarized Affidavit of Certification.
- Signed and notarized Affidavit of Non-Interest for each owner.
- Customer references with contact name, phone number, and email address.
- Proof business existed six months before application date, or company invoice and proof of payment if less than six months old.
- Company federal tax returns and related schedules for the past five years, including extension requests.
- Documented proof of contributions used to acquire ownership for each owner.
- Resumes for all owners, officers, and key personnel.
- Both sides of all corporate stock certificates and the stock transfer ledger.
- Corporate bank resolution and bank signature cards.
- Corporate bylaws and amendments.
- Official Articles of Incorporation or Certificate of Formation.
- Proof of vendor/supplier registration with City of Houston Strategic Purchasing Division.

## Company Onboarding Checklist

Use this once per company before starting certification submissions:

- [ ] Legal name.
- [ ] DBA names.
- [ ] EIN/TIN.
- [ ] State of formation.
- [ ] Physical address.
- [ ] Mailing address.
- [ ] Bank account for federal payment.
- [ ] Owners, ownership percentages, titles, and citizenship/residency facts.
- [ ] Operating agreement, bylaws, shareholder agreement, or equivalent.
- [ ] Tax returns and financial statements.
- [ ] Primary and secondary NAICS codes.
- [ ] Existing SAM.gov UEI/CAGE status.
- [ ] Existing state/local certification status.
- [ ] Evidence root folder.

## Intake Workflow

1. Add the company to `data/companies.csv`.
2. Copy the `metro_lecrown` intake rows in `data/company-intake.csv` for that
   company.
3. Fill values that are safe to track in CSV.
4. For sensitive values, put the value in `.local/` or the proper private
   document store and write the path or owner in the CSV.
5. Add every supporting document to `data/evidence-register.csv`.
6. Only then update `data/company-certifications.csv` with active certification
   lanes.

Do not enter full bank account numbers, SSNs, passwords, or portal recovery
answers in CSV files.

## Reusable Document Workflow

Use this before uploading documents to any portal:

1. Put each common document into `data/reusable-documents.csv`.
2. Mark whether it is reusable as-is, reusable after date refresh, or
   certification-specific.
3. Link the actual file path in `data/evidence-register.csv` if the file exists.
4. Use `data/document-requirement-map.csv` to see which certifications and
   buyers depend on the same document.
5. Work the highest-leverage missing documents first.

High-leverage reusable documents usually include:

- Legal formation documents.
- EIN/TIN confirmation.
- W-9.
- Ownership ledger or ownership schedule.
- Operating agreement, bylaws, or shareholder agreement.
- Owner/officer resumes.
- Capability statement.
- NAICS/NIGP commodity-code list.
- SAM.gov UEI and CAGE proof.
- CMBL/HUB/VetHUB proof where applicable.
- Tax returns.
- Balance sheet and profit/loss statement.
- Bank resolution or authorized signer proof.
- Insurance certificates.
- Licenses, permits, bonding, and professional credentials.
- Customer references.
- Personal net worth statements where an owner-based certification requires
  them.

Sensitive documents should be tracked by storage location and owner, not copied
into public CSV fields.

## Document Portal Workflow

The LeCrown document portal is the storage target for reusable certification and
buyer documents once a portal project exists. It is project-scoped,
authenticated, and supports admin uploads and authenticated downloads.

Portal reference:

- Portal login: `https://lecrowndevelopment.com/portal/login`
- Backend/API owner: `lecrowndevelopment-lead-api`
- Upload route: `POST /v1/portal/projects/:projectId/documents`
- Required upload payload fields: `name`, `category`, and `contentBase64`
- Optional upload payload fields: `id`, `fileName`, `contentType`,
  `description`
- Fortress Phronesis portal package:
  `/Users/benjaminlagrone/Documents/projects/pericopeai.com/fortress-phronesis/ops/lecrown-portal/metro-lecrown-certification-tracker`

Operating rules:

1. Put approved storage targets in `data/document-storage-locations.csv`.
2. For each reusable document, create or update one row in
   `data/document-portal-map.csv`.
3. Use `source_of_truth` values consistently:
   - `local`: source file lives in this project.
   - `private_local`: source file lives in `.local/` or another private local
     location.
   - `drive`: source file lives in Google Drive and is tracked by file ID, not
     public URL.
   - `portal`: the LeCrown portal record is the operational source.
   - `drive_backed_portal_record`: the portal stores the file in Drive, but the
     portal record remains the access point.
   - `external`: the file or confirmation lives in a buyer/certification
     portal.
   - `missing`: the document has not been created or found.
4. Do not store public or tokenized download URLs in CSV files.
5. Store portal project IDs, portal document IDs, Drive file IDs if returned by
   the portal, local paths, and last sync dates.
6. Upload sensitive records only to the exact portal project or external portal
   that requires them.
7. Keep passwords, bank values, SSNs, tax return contents, and recovery answers
   out of all tracker CSVs.

The portal map answers: "Where is this document now, where should it live, and
what ID proves it has been uploaded?"

## Capability Statement Workflow

Capability statements are required bid-readiness assets, not optional marketing
collateral. Track them like certification evidence.

Files:

- `data/capability-statements.csv`: statement inventory and next actions.
- `docs/capability-statements/`: markdown source drafts and templates.
- `data/document-portal-map.csv`: portal upload target and returned IDs.

Rules:

1. Maintain one master statement per company.
2. Create buyer-specific versions when the buyer has different language,
   commodity codes, or certifications.
3. Do not claim certifications until they are approved.
4. Do not invent past performance. Use `TBD` until references are confirmed.
5. Export final versions to PDF, then upload them through the portal or buyer
   portal that needs them.
6. Refresh every quarter or whenever services, NAICS/NIGP codes,
   certifications, insurance, or references change.

Current Metro LeCrown drafts:

- `docs/capability-statements/metro-lecrown-master.md`
- `docs/capability-statements/metro-lecrown-city-houston-draft.md`
- `docs/capability-statements/metro-lecrown-metro-draft.md`
- `docs/capability-statements/metro-lecrown-universities-draft.md`
- `docs/capability-statements/metro-lecrown-tdcj-draft.md`

## Buyer Requirements Workflow

Use this for every agency, university, city, county, school district, or prime
contractor in the opportunity tracker:

1. Add the buyer to `data/buyers.csv`.
2. Identify the buyer's public procurement portal and bid source.
3. Identify whether the buyer requires a statewide registration such as CMBL,
   an internal vendor setup process, a supplier diversity profile, a subcontracting
   plan, or a disclosure form.
4. Add each requirement as a row in
   `data/buyer-certification-requirements.csv`.
5. Tie each requirement to every company that can pursue that buyer.
6. Mark requirements as `required`, `recommended`, `conditional`, or
   `opportunity_specific`.

The buyer requirement layer answers: "What must this company have ready before
we can credibly bid this buyer?"

## Seed Buyer Notes

| Buyer | Required/Recommended Gates | Immediate Action |
| --- | --- | --- |
| University of Houston | Texas CMBL recommended for state bid discovery; ESBD is used for current bid opportunities; UH vendor setup/payment process applies when doing business; Form 1295 may apply to certain contracts. | Register or verify CMBL, monitor UH ESBD opportunities, prepare vendor setup data. |
| University of Texas at Austin | UT uses Bonfire for bid opportunities, has Vendor Management/VID/PIF processes, tracks VetHUB participation through B2Gnow, and lists small business/subcontracting certification categories for federal work. | Register/monitor UT Bonfire, prepare PIF/VID data, verify CMBL/VetHUB/SB status. |

## Federal Foundation

### SAM.gov Entity Registration

Source: https://sam.gov/entity-registration

Purpose: required for organizations that want to directly bid on government
contracts or apply for federal assistance.

Checklist:

- [ ] Confirm legal business name and physical address.
- [ ] Confirm Taxpayer Identification Number/EIN.
- [ ] Confirm ownership and entity details.
- [ ] Confirm bank account details for electronic funds transfer.
- [ ] Confirm NAICS codes.
- [ ] Confirm points of contact.
- [ ] Register entity or renew entity in SAM.gov.
- [ ] Save Unique Entity ID.
- [ ] Save CAGE code if assigned.
- [ ] Save registration activation date.
- [ ] Save renewal deadline. SAM.gov registration must be renewed every 365
      days to stay active.

Notes:

- SAM.gov says registration can take up to 10 business days to become active.
- A Unique Entity ID alone is not enough to apply directly for federal awards.

### NAICS And Capability Profile

Purpose: certification applications and contracting searches depend on the
business being classified accurately.

Checklist:

- [ ] Pick primary NAICS code.
- [ ] Pick secondary NAICS codes.
- [ ] Confirm SBA size standard for each target NAICS.
- [ ] Draft one-page capability statement.
- [ ] Define core offerings, differentiators, past performance, service area,
      and contact information.
- [ ] Prepare DSBS profile content after SAM.gov is active.

## SBA Certifications

Source: https://www.sba.gov/federal-contracting/contracting-assistance-programs

SBA notes that many contracting assistance programs require certification, and
many use MySBA Certifications for eligibility checks and applications.

### MySBA Certifications

Portal: https://certifications.sba.gov/

Checklist:

- [ ] Create/login to account.
- [ ] Add business profile.
- [ ] Run WOSB/EDWOSB eligibility questionnaire.
- [ ] Run 8(a) eligibility questionnaire.
- [ ] Run HUBZone eligibility questionnaire.
- [ ] Download program-specific checklists.
- [ ] Save all portal confirmation screenshots or PDFs.

### WOSB / EDWOSB

Source: https://www.sba.gov/federal-contracting/contracting-assistance-programs/women-owned-small-business-federal-contract-program

Purpose: compete for WOSB set-aside contracts if the business qualifies.

Gate questions:

- [ ] Is the business at least 51% women-owned?
- [ ] Does the qualifying woman owner control daily operations and long-term
      decisions?
- [ ] Does the qualifying woman owner hold the highest officer position?
- [ ] Does the qualifying woman owner work full time during normal business
      hours?
- [ ] For EDWOSB, do personal net worth, adjusted gross income, and asset tests
      meet the current SBA thresholds?

Submission checklist:

- [ ] Confirm qualifying owner.
- [ ] Prepare governing documents.
- [ ] Prepare ownership evidence.
- [ ] Prepare resumes.
- [ ] Prepare tax returns and financial statements if required.
- [ ] Prepare PNW for EDWOSB if applicable.
- [ ] Submit in MySBA Certifications.
- [ ] Track analyst questions.
- [ ] Save approval or denial letter.

Maintenance:

- [ ] Record certification date.
- [ ] Record anniversary date.
- [ ] Record three-year program examination/recertification date.
- [ ] Recheck SBA maintenance rules before each anniversary.

### 8(a) Business Development

Source: https://www.sba.gov/federal-contracting/contracting-assistance-programs/8a-business-development-program

Purpose: business development and federal contracting program for experienced
small business owners who are socially and economically disadvantaged.

SBA's application sequence:

- [ ] Identify primary NAICS code or codes.
- [ ] Register business in SAM.gov.
- [ ] Apply for 8(a) certification through MySBA Certifications.

Readiness checklist:

- [ ] Confirm business has enough operating history and past performance to be
      ready for federal contracting.
- [ ] Confirm qualifying owner and control facts.
- [ ] Prepare social disadvantage narrative/evidence if required.
- [ ] Prepare economic disadvantage evidence.
- [ ] Prepare personal financial statements.
- [ ] Prepare tax returns.
- [ ] Prepare business formation and ownership documents.
- [ ] Meet with SBA District Office or APEX Accelerator counselor before
      submitting.
- [ ] Submit application.
- [ ] Track analyst questions.
- [ ] Save approval or denial letter.

Maintenance:

- [ ] Record program entry date.
- [ ] Record annual review date.
- [ ] Track business plan updates and program obligations.

### HUBZone

Source: https://www.sba.gov/federal-contracting/contracting-assistance-programs/hubzone-program

Purpose: compete for HUBZone set-aside contracts and receive price evaluation
preference when qualified.

Eligibility gates:

- [ ] Business is small under SBA size standards.
- [ ] Business is at least 51% owned and controlled by eligible owners.
- [ ] Principal office is in a HUBZone.
- [ ] At least 35% of employees live in a HUBZone.

Submission checklist:

- [ ] Check principal office address on SBA HUBZone map.
- [ ] Check employee addresses on SBA HUBZone map.
- [ ] Prepare lease/deed or office evidence.
- [ ] Prepare payroll and employee residency evidence.
- [ ] Submit in MySBA Certifications.
- [ ] Track analyst questions.
- [ ] Save approval or denial letter.

Maintenance:

- [ ] Record certification date.
- [ ] Record three-year recertification date.
- [ ] Recheck map status and employee residency before major bids.

## Local And State Certifications

### City Of Houston OBO M/WBE, SBE, Or Related Certification

Working assumption: this project already contains Houston-related certification
materials based on `.local/houston-mwdbe.credentials`, affidavit PDFs, and PNW
PDFs. Do not copy credentials into this document.

Checklist:

- [ ] Log into the Houston certification portal.
- [ ] Record exact certification type being pursued.
- [ ] Record application number.
- [ ] Record current application status.
- [ ] Confirm required affidavit is final.
- [ ] Confirm PNW forms are final for each required owner.
- [ ] Identify remaining document requests.
- [ ] Submit missing documents.
- [ ] Track analyst questions.
- [ ] Save certification letter and expiration date.

### Texas HUB

Checklist:

- [ ] Confirm eligibility category.
- [ ] Confirm Texas principal place of business requirement.
- [ ] Gather ownership/control documents.
- [ ] Gather tax and formation documents.
- [ ] Submit application through the official state route.
- [ ] Save certification proof and expiration date.
- [ ] Add renewal date to the dashboard.

### TxDOT DBE / ACDBE

Checklist:

- [ ] Decide whether transportation contracts are a target market.
- [ ] Confirm DBE/ACDBE eligibility.
- [ ] Gather PNW, tax, ownership, control, and business capability evidence.
- [ ] Submit only if the opportunity lane justifies the documentation burden.
- [ ] Save certification proof and expiration date.

## Evidence Register

| Evidence | Path | Status | Notes |
| --- | --- | --- | --- |
| Affidavit of Certification | `Affidavit_of_Certification.pdf` | Existing | Source PDF |
| Jie Huang signed/filled affidavit | `output/pdf/Affidavit_of_Certification_Jie_Huang_President.pdf` | Existing | Likely Houston/OBO evidence |
| Benjamin PNW final | `output/pdf/PNW_Benjamin_LaGrone_FINAL.pdf` | Existing | Confirm if required for each application |
| Jie Huang PNW final | `output/pdf/PNW_Jie_Huang_FINAL.pdf` | Existing | Confirm if required for WOSB/EDWOSB, 8(a), local cert |
| Updated PNW form | `Updated_PNW_Form.pdf` | Existing | Source/blank or updated form |
| Houston credentials | `.local/houston-mwdbe.credentials` | Sensitive | Do not copy into tracked docs |

## Weekly Review

Use this review every Friday until certifications are active:

- [ ] What certification moved this week?
- [ ] What portal is waiting on us?
- [ ] What portal or analyst are we waiting on?
- [ ] What document is missing?
- [ ] What deadline is within 14 days?
- [ ] What is the one submission we will finish next week?
