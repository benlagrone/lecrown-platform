"""Explainable, uncalibrated pursuit ranking; never an asserted win percentage."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime

FACTOR_NAMES = {"capability", "ai_leverage", "owner_leverage", "reuse", "barriers", "cash_structure", "reference", "follow_on"}


def validate_model(model: dict) -> None:
    if set(model["weights"]) != {"win", "profitability", "potential"}:
        raise ValueError("Expected all three ranking dimensions")
    if abs(sum(model["weights"].values()) - 1) > 1e-8 or any(v < 0 for v in model["weights"].values()):
        raise ValueError("Weights must be nonnegative and total one")
    ids = set()
    for profile in model["profiles"]:
        if profile["id"] in ids or set(profile["factors"]) != FACTOR_NAMES:
            raise ValueError("Duplicate profile or incomplete factor rubric")
        ids.add(profile["id"])
        re.compile(profile["pattern"])
        if any(type(v) not in {int, float} or not 0 <= v <= 5 for v in profile["factors"].values()):
            raise ValueError("Factors must be on the declared 0-5 scale")


def model_hash(model: dict) -> str:
    return hashlib.sha256(json.dumps(model, sort_keys=True).encode()).hexdigest()


def input_hash(record: dict) -> str:
    keys = ("id", "name", "description", "stage", "amount", "amountCurrency", "closeDate", "probability")
    return hashlib.sha256(json.dumps({k: record.get(k) for k in keys}, sort_keys=True).encode()).hexdigest()


def metadata_lines(record: dict) -> dict[str, str]:
    result = {}
    for line in (record.get("description") or "").splitlines():
        key, sep, value = line.partition(": ")
        if sep:
            result[key] = value.strip()
    return result


def assessment(record: dict, evidence: dict, model: dict, as_of: date) -> dict:
    title = unicodedata.normalize("NFKC", record.get("name") or "").casefold()
    profile = next((p for p in model["profiles"] if re.search(p["pattern"], title)), None)
    meta = metadata_lines(record)
    observed = evidence.get(record["id"], {})
    evidence_date = observed.get("checked_at", "")[:10]
    fresh = False
    if evidence_date:
        age = (as_of - date.fromisoformat(evidence_date)).days
        fresh = 0 <= age <= model.get("evidence_max_age_days", 2)
    public_status = observed.get("status", "unavailable") if fresh else "unavailable"
    public_project = observed.get("project") or {}
    raw_due = public_project.get("DateClose") if fresh else None
    raw_due = raw_due or meta.get("Due Date", "")
    due_match = re.match(r"(\d{4}-\d{2}-\d{2})", raw_due or "")
    due_date = date.fromisoformat(due_match[1]) if due_match else None
    days = (due_date - as_of).days if due_date else None
    is_forecast = "forecast" in meta.get("Status", "").casefold()
    is_rfi = bool(re.match(r"RFI\b", meta.get("Solicitation ID", ""), re.I))
    explicit_sub = bool(re.search(r"\bsubcontract(?:ing|or)?\b", meta.get("Status", ""), re.I))
    flags = [
        "Actual contract revenue, profit, founder hours, compute costs and peak cash shortfall are unqualified.",
        "Full solicitation, amendments, eligibility and mandatory staffing/product terms require review.",
    ]
    status = "Prime - source review"
    readiness = 1
    if is_forecast or is_rfi:
        status, readiness = "Prime - capture", 2
    elif public_status == "listed_open" and (days is None or days >= 0):
        status, readiness = "Prime - qualify", 4
    if days is not None and days < 0:
        status, readiness = "Hold - deadline review", 0
        flags.append("Stored or public-list deadline has passed; verify amendments/reopening before any bid.")
    if public_status == "not_in_open_list":
        status, readiness = "Hold - not listed open", 0
        flags.append("Absent from the buyer's complete public open list; absence is not proof of an award or cancellation.")
    if explicit_sub and status.startswith("Prime"):
        status = "Sub - qualify"
    if days is not None and 0 <= days <= 1 and not is_forecast:
        readiness = min(readiness, 1)
        flags.append("Deadline is today or tomorrow: confirm exact portal time/time zone and existing readiness immediately.")
    if is_rfi:
        flags.append("RFI capture response is not a current paid-contract bid.")
    if is_forecast:
        flags.append("Forecast is not a released solicitation; no current bid submission is established.")
    if public_status == "unavailable":
        flags.append("Live listing status is unavailable or stale; CRM text alone does not establish bid availability.")
    if record.get("stage") in {"Closed Won", "Closed Lost"}:
        status, readiness = "Closed - CRM", 0
    if not profile:
        return {
            "id": record["id"], "name": record.get("name"), "status": "Review - unmapped",
            "win": None, "profitability": None, "potential": None, "priority": None,
            "flags": flags + ["No reviewed capability profile matches this record; do not fabricate a score."],
            "checks": ["Review the scope and extend the versioned model."], "confidence": "Low",
            "input_hash": input_hash(record), "profile": None, "due_date": str(due_date) if due_date else None,
            "source_url": meta.get("Source URL"), "public_status": public_status,
        }
    if profile.get("out_of_scope"):
        status = "Review - outside core scope"
    f = profile["factors"]
    win = round(20 * (.35*f["capability"] + .25*f["owner_leverage"] + .2*f["barriers"] + .2*readiness))
    profitability = round(20 * (.4*f["ai_leverage"] + .25*f["owner_leverage"] + .2*f["reuse"] + .15*f["cash_structure"]))
    potential = round(20 * (.4*f["reference"] + .35*f["reuse"] + .25*f["follow_on"]))
    priority = round(win*model["weights"]["win"] + profitability*model["weights"]["profitability"] + potential*model["weights"]["potential"])
    if profile["id"] in {"energy_integration", "facility_it"}:
        flags.append("Physical work/equipment is a separately quoted scope; no field contractor price is assumed.")
    return {
        "id": record["id"], "name": record.get("name"), "profile": profile["id"], "status": status,
        "win": win, "profitability": profitability, "potential": potential, "priority": priority,
        "factors": {**f, "readiness": readiness}, "reason": profile["reason"], "checks": profile["checks"],
        "flags": flags, "confidence": "Low", "input_hash": input_hash(record),
        "due_date": str(due_date) if due_date else None, "source_url": meta.get("Source URL"),
        "public_status": public_status, "evidence": observed if fresh else {},
        "win_probability_percent": None, "financial_profit_usd": None,
        "assumed_software_contractor_cost_usd": 0,
    }


def rank(records: list[dict], evidence: dict, model: dict, as_of: date) -> list[dict]:
    validate_model(model)
    if len(records) != len({r["id"] for r in records}):
        raise ValueError("Duplicate Opportunity IDs")
    rows = [assessment(record, evidence, model, as_of) for record in records]
    # Prime paths precede subs; unavailable/closed/out-of-scope records cannot win on attractive keywords.
    status_order = {"Prime - qualify": 0, "Prime - capture": 1, "Prime - source review": 2,
                    "Sub - qualify": 3, "Review - unmapped": 4, "Hold - deadline review": 5,
                    "Hold - not listed open": 5, "Closed - CRM": 6, "Review - outside core scope": 7}
    rows.sort(key=lambda r: (status_order[r["status"]], -(r["priority"] or 0), -(r["win"] or 0),
                             -(r["profitability"] or 0), r["name"].casefold(), r["id"]))
    for number, row in enumerate(rows, 1):
        row["rank"] = number
    return rows


def crm_values(row: dict, model: dict, assessed_at: datetime) -> dict:
    lines = [
        f"Model: {model['version']} | Assessed: {assessed_at.isoformat()}",
        "SCORES ARE HEURISTICS /100, NOT CALIBRATED WIN PERCENTAGES OR PROVEN FINANCIAL RETURNS.",
        f"Rank {row['rank']}; {row['status']}; composite {row['priority']}; confidence {row['confidence']}.",
        f"Win likelihood {row['win']}; profitability potential {row['profitability']}; strategic potential {row['potential']}.",
        f"Weights: win {model['weights']['win'] * 100:g}%, profitability potential {model['weights']['profitability'] * 100:g}%, strategic potential {model['weights']['potential'] * 100:g}%; pursuit gates and prime-first sorting precede the composite.",
        model["delivery_model"], model["financial_policy"],
        "Five-plus monthly engagements is a target scenario, not a forecast of wins or proven throughput.",
        "Your compensation is not a residual or a discounted hourly-rate assumption.",
        "PROFILE JUDGMENT: " + row.get("reason", "Unmapped scope; scores intentionally unknown."),
        "These factors infer suitability from the title/saved scope; they are not verified procurement requirements.",
        "Factor rubric (0-5): " + json.dumps(row.get("factors", {}), sort_keys=True),
        "WIN = 20 x (0.35 capability + 0.25 owner leverage + 0.20 entry-barrier ease + 0.20 readiness).",
        "PROFIT POTENTIAL = 20 x (0.40 AI leverage + 0.25 owner leverage + 0.20 reuse + 0.15 cash-cost structure).",
        "STRATEGIC POTENTIAL = 20 x (0.40 reference value + 0.35 reuse + 0.25 follow-on potential).",
        "Financial feasibility: UNVERIFIED. Revenue, owner compensation, actual margin and funding must be qualified, not guessed.",
        "NEXT CHECKS:", *["- " + check for check in row["checks"]],
        "LIMITS / FLAGS:", *["- " + flag for flag in row["flags"]],
        "Source: " + (row.get("source_url") or "Not supplied"),
        "Live evidence: " + json.dumps(row.get("evidence", {}), sort_keys=True),
        "Guides (methodology, not endorsements of scores or weights):", *model["sources"],
        "Model SHA-256: " + model_hash(model),
    ]
    return {
        "cPursuitRank": row["rank"], "cWinLikelihoodScore": row["win"],
        "cProfitabilityPotential": row["profitability"], "cStrategicPotential": row["potential"],
        "cPursuitPriority": row["priority"], "cPursuitStatus": row["status"],
        "cPursuitConfidence": row["confidence"], "cPursuitAssessment": "\n\n".join(lines),
        "cPursuitAssessedAt": assessed_at.strftime("%Y-%m-%d %H:%M:%S"),
    }
