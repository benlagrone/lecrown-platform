# AI-first CRM Pursuit Scoring

LeCrown's first-contract ranking uses Benjamin's technical and delivery leadership,
Sextant/AI production, and no assumed software contractor labor. Prime pursuits
precede subcontracting. New-energy project leadership and systems integration
remain in scope; physical installation is separately scoped specialist work.

The versioned rubric is `platform/backend/app/resources/crm-pursuit-model.json`. This is an initial
explainable heuristic, not a calibrated probability model or verified profit
forecast. Buyer documents control eligibility, permitted AI usage, staffing,
product authorizations, pricing and submission requirements.

## Scores and Gates

Factors use 0-5 analyst judgments based on saved scope/title and the user-confirmed
capability profile. A full-package review can change any factor. The assessment
discloses every factor, source, evidence timestamp and next qualification check.

- Win likelihood score: 35% capability alignment, 25% founder/small-team
  feasibility, 20% expected ease of entry, 20% pursuit readiness.
- Profitability potential: 40% AI production leverage, 25% founder-time leverage,
  20% reuse, 15% cash-cost structure. This is structural potential, not an actual
  margin, owner compensation estimate or guarantee of a viable price.
- Strategic potential: 40% reference value, 35% reusable assets, 25% follow-on
  potential. These are judgments, not established follow-on awards.
- Composite: 50% win likelihood, 30% profitability potential, 20% strategic
  potential. Equal composites use win likelihood and then profitability to break
  ties. Weights are an explicit initial implementation choice, not sourced rates.
- Sort gates precede the composite: prime qualification, prime capture, prime
  source review, subcontract qualification, unmapped review, deadline/not-open
  holds, closed CRM records, and outside-core review.

Forecasts and RFIs remain capture opportunities, not current paid-contract bids.
A public open listing confirms visibility only, not eligibility or complete
document access. Source snapshots older than two days cannot establish current
availability. Exact deadline time zones and amendments require checking the
buyer portal. Same-day/tomorrow deadlines reduce readiness.

Unknown scope stays unscored; it is not silently assigned a generic positive
score. All initial assessments carry Low confidence because package review,
financial feasibility and competitive history are incomplete.

No invented contractor budget, owner hourly rate, price minimum, revenue, dollar
profit, or five-awards-per-month forecast is used. Founder time, compute,
licenses, support, overhead and funding remain real inputs to qualify. AI savings
can improve margins without implying a lower selling price or lower value for
the founder's expertise.

## Repeatable Operation

Use the backend Python environment with its existing `requests` and
`python-dotenv` dependencies. Credentials remain in the explicitly supplied
environment file, never in source, output or command arguments.

```bash
PYTHONPATH=platform/backend python scripts/score-crm-opportunities.py preview \
  --env-file /absolute/path/to/authorized.env \
  --refresh-evidence \
  --output-dir /private/path/to/review
```

Preview reads every existing EspoCRM Opportunity through a complete, stable,
deduplicated pagination snapshot. It refreshes up to 20 public Bonfire buyer
hosts with six-second pacing, stops on 429, and never forwards CRM credentials
to a public portal. An explicit `--evidence-dir` can reuse the collector's raw
portal snapshots; freshness checks still apply. No flag follows private project
links, bypasses access controls or enrolls a vendor.

Read `RANKING.md` and `ranking.json`, then explicitly apply the bounded plan:

```bash
PYTHONPATH=platform/backend python scripts/score-crm-opportunities.py apply \
  --env-file /absolute/path/to/authorized.env \
  --plan /private/path/to/review/ranking.json \
  --expected-count 22 \
  --configure-fields \
  --output-dir /private/path/to/apply-receipt
```

Replace the expected count with the reviewed live count, never a guessed count.
Preview expires after two hours. Apply rejects changed IDs/content, conflicting
field types, non-score writes and duplicate ranks. It rechecks each record before
writing and reads back every result plus the complete final list. An uncertain
PUT is reconciled by GET, not blindly retried.

`--configure-fields` uses EspoCRM's existing administrator Field Manager and Layout
APIs to add nine business-assessment fields and list/detail/filter layouts. This
is an authorized CRM configuration/data operation, not an alternative VPS release
or application deployment path. It changes no authentication, roles, credentials,
ports, containers, DNS, TLS or Properties runtime.

Opportunity names, descriptions, sales probability, amounts, currency, close
dates, stages and user fit ratings are preserved. Existing list columns remain
available as hidden optional columns where the ranking view needs space. The
native Probability field remains stage-based and distinct from the heuristic
Win Likelihood Score. The detail panel includes the full rubric and unknowns.
Click Pursuit Rank ascending in the Opportunity list to see the priority queue.

Snapshots and receipts are written mode 0600. They are private runtime artifacts,
not repository content. Keep before-records and schema/layout backups for audit.
Restoring earlier values is a separately authorized CRM operation. The manual
CLI remains available; automatic operation uses the separate worker below.

## Automatic Scoring

The Fortress-owned Development deployment runs `app.jobs.score_crm_opportunities`
as a persistent, portless `pursuit-ranker` service. Every 60 seconds it reads all
Opportunities, assesses new/edited records and repairs portfolio ranks after
additions or deletions. Time-sensitive readiness and expiry are recalculated in
America/Chicago even if nobody edits a record. Title matches take precedence;
saved description scope can match the same reviewed profiles when the title does not.
Unmapped scopes receive a rank and explicit review status, not invented scores.

The model's weights, AI-first delivery assumptions, no assumed software contractor
costs, and prime-first gates are unchanged. Amounts and expected sales close dates
are not treated as bid deadlines or fabricated margins. Known bid dates come from
the saved `Due Date:` metadata and fresh collector evidence. Exact portal times,
time zones and amendments still require package review.

The worker reuses complete Bonfire snapshots from the existing bounded collector
(15-minute batches, rotating buyers). It makes no extra portal requests and cannot
bypass rate limits. Source deadlines/status refresh when that buyer's next successful
snapshot arrives, not necessarily in the next batch. Unsupported/stale sources remain
flagged. Collection in progress uses only cached evidence for unchanged source URLs.

Private atomic state, before-records, pending write intent, verified receipts and
health live in `/app/data/crm-pursuit-scoring` on the existing persistent volume.
A single-worker file lock prevents overlap. Input fingerprints exclude score fields,
and unchanged results retain their original assessment timestamp and produce no PUTs.
Every changed write is read back; concurrent business edits abort the pass and trigger
a fresh snapshot, never a business-field overwrite. HTTP 429 respects Retry-After;
failures use exponential backoff and mark worker health unhealthy. No credentials,
accounts, layouts, stages, native sales probabilities or user fit ratings are changed.

## Validation

```bash
cd platform/backend
python -m unittest discover -s tests -p test_crm_pursuit_scoring.py -v
```

Tests cover finance unknowns, prime-first ordering, forecast/RFI gates, deadline
evidence, outside-scope handling, energy integration, score-only payloads and
fail-closed writes. Existing backend/frontend/tracker validation remains the
project-wide regression gate. Ranking scores need calibration against subsequent
qualified/no-bid/submitted/won/lost outcomes before they can be called actual
win probabilities.
