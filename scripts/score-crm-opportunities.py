#!/usr/bin/env python3
"""Preview and explicitly apply AI-first pursuit assessments to existing Espo Opportunities."""

from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "platform/backend"))
from app.services.crm_pursuit_scoring import crm_values, input_hash, metadata_lines, model_hash, rank

CRM = "https://crm.lecrowndevelopment.com"
SCORE_FIELDS = {
    "cPursuitRank": {"type": "int", "label": "Pursuit Rank", "min": 1},
    "cWinLikelihoodScore": {"type": "int", "label": "Win Likelihood Score", "min": 0, "max": 100},
    "cProfitabilityPotential": {"type": "int", "label": "AI Profit Potential", "min": 0, "max": 100},
    "cStrategicPotential": {"type": "int", "label": "Strategic Potential", "min": 0, "max": 100},
    "cPursuitPriority": {"type": "int", "label": "Weighted Priority", "min": 0, "max": 100},
    "cPursuitStatus": {"type": "enum", "label": "Pursuit Path", "options": [
        "Prime - qualify", "Prime - capture", "Prime - source review", "Sub - qualify", "Review - unmapped",
        "Hold - deadline review", "Hold - not listed open", "Closed - CRM", "Review - outside core scope",
    ]},
    "cPursuitConfidence": {"type": "enum", "label": "Assessment Confidence", "options": ["Low", "Moderate", "High"]},
    "cPursuitAssessment": {"type": "text", "label": "AI-first Pursuit Assessment"},
    "cPursuitAssessedAt": {"type": "datetime", "label": "Pursuit Assessed At"},
}


def write_private(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
    os.chmod(path, 0o600)


class Client:
    def __init__(self, env_file):
        env = dotenv_values(env_file)
        self.username = env.get("ESPOCRM_USERNAME") or env.get("ESPOLOGIN")
        password = env.get("ESPOCRM_PASSWORD") or env.get("ESPOPW")
        if not self.username or not password:
            raise ValueError("Existing EspoCRM credentials are required")
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"
        self.session.headers["Espo-Authorization"] = self.auth(password)
        result = self.call("GET", "/App/user")
        self.session.headers["Espo-Authorization"] = self.auth(result["token"])
        self.is_admin = result.get("user", {}).get("type") == "admin"

    def auth(self, credential):
        return base64.b64encode((self.username + ":" + credential).encode()).decode()

    def call(self, method, path, **kwargs):
        try:
            result = self.session.request(method, CRM + "/api/v1" + path, timeout=60, allow_redirects=False, **kwargs)
        except requests.RequestException as exc:
            raise RuntimeError(f"CRM {method} {path} failed; writes must be read back before retry") from exc
        if not 200 <= result.status_code < 300:
            raise RuntimeError(f"CRM {method} {path} returned {result.status_code}")
        return result.json()

    def opportunities(self):
        rows, expected, ids = [], None, set()
        while expected is None or len(rows) < expected:
            body = self.call("GET", "/Opportunity", params={"maxSize": 200, "offset": len(rows), "orderBy": "id", "order": "asc"})
            batch, total = body.get("list"), body.get("total")
            if not isinstance(batch, list) or type(total) is not int or total < 0 or (expected is not None and total != expected):
                raise ValueError("Invalid or changing CRM snapshot")
            expected = total
            for row in batch:
                if not row.get("id") or row["id"] in ids:
                    raise ValueError("Missing or duplicate CRM ID")
                ids.add(row["id"])
            rows.extend(batch)
            if len(rows) > total or (not batch and len(rows) != total):
                raise ValueError("Incomplete CRM pagination")
        return rows


def live_evidence(records, directory):
    if directory is None:
        return {}
    evidence = json.loads((directory / "source-evidence.json").read_text())
    checked = {}
    for row in records:
        item = copy.deepcopy(evidence.get(row["id"]))
        if not item:
            continue
        host = urlparse(metadata_lines(row).get("Source URL", "")).hostname
        expected = f"https://{host}/PublicPortal/getOpenPublicOpportunitiesSectionData"
        if not host or not host.endswith(".bonfirehub.com") or item.get("url") != expected:
            raise ValueError("Source evidence does not match the saved buyer URL")
        file = directory / ("portal-" + host + ".json")
        if file.exists():
            payload = json.loads(file.read_text())
            projects = payload.get("payload", {}).get("projects")
            if payload.get("success") != 1 or not isinstance(projects, (dict, list)):
                raise ValueError("Malformed public evidence snapshot")
            if isinstance(projects, dict):
                projects = list(projects.values())
            project_id = urlparse(metadata_lines(row)["Source URL"]).path.rsplit("/", 1)[-1]
            matches = [p for p in projects if str(p.get("ProjectID")) == project_id and str(p.get("ProjectVisibilityID", "1")) == "1"]
            item["status"] = "listed_open" if matches else "not_in_open_list"
            item["project"] = matches[0] if matches else None
            item["checked_at"] = datetime.fromtimestamp(file.stat().st_mtime, timezone.utc).isoformat()
        else:
            item["status"] = "unavailable"
        checked[row["id"]] = item
    return checked


def collect_evidence(records, directory):
    directory.mkdir(parents=True, exist_ok=True)
    buyers = {}
    for row in records:
        source = urlparse(metadata_lines(row).get("Source URL", ""))
        if source.scheme == "https" and source.hostname and re_full_bonfire(source.hostname):
            buyers.setdefault(source.hostname, []).append(row["id"])
    evidence = {}
    for index, (host, record_ids) in enumerate(buyers.items()):
        if index >= 20:
            break
        url = f"https://{host}/PublicPortal/getOpenPublicOpportunitiesSectionData"
        try:
            response = requests.get(url, headers={"Accept": "application/json", "User-Agent": "LeCrown-Pursuit-Review/1.0"}, timeout=30, allow_redirects=False)
            if response.status_code == 429:
                for record_id in record_ids:
                    evidence[record_id] = {"url": url, "status": "unavailable", "error": "429; collection deferred without bypass"}
                break
            response.raise_for_status()
            payload = response.json()
            if payload.get("success") != 1 or not isinstance(payload.get("payload", {}).get("projects"), (dict, list)):
                raise ValueError("Malformed public source snapshot")
            write_private(directory / ("portal-" + host + ".json"), payload)
            for record_id in record_ids:
                evidence[record_id] = {"url": url, "status": "collected"}
        except (requests.RequestException, ValueError) as error:
            for record_id in record_ids:
                evidence[record_id] = {"url": url, "status": "unavailable", "error": type(error).__name__}
        write_private(directory / "source-evidence.json", evidence)
        time.sleep(6)
    write_private(directory / "source-evidence.json", evidence)


def re_full_bonfire(host):
    return bool(re.fullmatch(r"[a-z0-9-]+\.bonfirehub\.com", host))


def preview(client, model, output, evidence_dir, refresh_evidence=False):
    records = client.opportunities()
    now = datetime.now(timezone.utc)
    as_of = now.astimezone(__import__("zoneinfo").ZoneInfo("America/Chicago")).date()
    if refresh_evidence:
        evidence_dir = output / "evidence"
        collect_evidence(records, evidence_dir)
    evidence = live_evidence(records, evidence_dir)
    ranked = rank(records, evidence, model, as_of)
    result = {
        "model_version": model["version"], "model_hash": model_hash(model), "created_at": now.isoformat(),
        "as_of": as_of.isoformat(), "count": len(records), "rows": ranked,
        "updates": {r["id"]: crm_values(r, model, now) for r in ranked},
        "inputs": {r["id"]: input_hash(r) for r in records},
    }
    write_private(output / "crm-before.json", records)
    write_private(output / "ranking.json", result)
    lines = ["# LeCrown AI-first CRM Pursuit Ranking", "", f"Assessed {as_of}; model `{model['version']}`.", "",
             "Founder-led, Sextant/AI-built; zero assumed software contractor labor. No owner-rate or contract-price floor is imposed. Actual costs, founder hours and owner income remain to be qualified.", "",
             "Scores /100 are transparent analyst heuristics, NOT win percentages or established financial margins. All assessments are low confidence until package review. Prime paths precede subcontract paths; closed/unavailable and outside-core records cannot lead on keyword fit alone.", "",
             "| Rank | Opportunity | Path | Win | Profit potential | Strategic | Weighted |", "|---:|---|---|---:|---:|---:|---:|"]
    for row in ranked:
        name = (row["name"] or "").replace("|", "\\|")
        lines.append(f"| {row['rank']} | [{name}]({CRM}/#Opportunity/view/{row['id']}) | {row['status']} | {row['win']} | {row['profitability']} | {row['potential']} | {row['priority']} |")
    for row in ranked:
        lines += ["", f"## {row['rank']}. {row['name']}", "", row.get("reason", "Requires manual profile review."), "",
                  f"Source status: {row['public_status']}. Stored/public-list deadline date: {row['due_date'] or 'unknown'}; exact time zone and amendments require package review.", "",
                  *["- " + item for item in row["checks"]], *["- " + flag for flag in row["flags"]]]
    (output / "RANKING.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"count": len(records), "preview": str(output / "ranking.json"), "top": [{k:r[k] for k in ["rank", "name", "status", "win", "profitability", "potential", "priority"]} for r in ranked[:8]]}, indent=2))


def configure(client, output):
    if not client.is_admin:
        raise ValueError("Existing CRM administrator access is required for fields/layouts")
    metadata = client.call("GET", "/Metadata")
    existing = metadata["entityDefs"]["Opportunity"]["fields"]
    layouts = {name: client.call("GET", "/Opportunity/layout/" + name) for name in ["list", "detail", "filters"]}
    if not (output / "schema-layout-before.json").exists():
        write_private(output / "schema-layout-before.json", {"fields": existing, "layouts": layouts})
    for name, definition in SCORE_FIELDS.items():
        if name in existing:
            if existing[name]["type"] != definition["type"]:
                raise ValueError("Conflicting existing score field: " + name)
            continue
        # Espo's native field manager adds the custom c prefix and rebuilds this entity.
        native_name = name[1].lower() + name[2:]
        client.call("POST", "/Admin/fieldManager/Opportunity", json={"name": native_name, **definition})
        check = client.call("GET", "/Metadata")["entityDefs"]["Opportunity"]["fields"]
        if check.get(name, {}).get("type") != definition["type"]:
            raise ValueError("Created CRM field did not read back: " + name)
        print("Verified field " + name, flush=True)
    visible_scores = [
        {"name": "cPursuitRank", "width": 7}, {"name": "cWinLikelihoodScore", "width": 9},
        {"name": "cProfitabilityPotential", "width": 9}, {"name": "cStrategicPotential", "width": 9},
        {"name": "cPursuitStatus", "width": 17},
    ]
    names = {item["name"] for item in visible_scores}
    base = [copy.deepcopy(item) for item in layouts["list"] if item["name"] not in names]
    for item in base:
        if item["name"] in {"account", "assignedUser", "createdAt", "closeDate", "amount"}:
            item["hidden"] = True
        if item["name"] == "name":
            item["width"] = 35
        if item["name"] == "stage":
            item["width"] = 10
    listing = visible_scores[:1] + base[:1] + visible_scores[1:] + base[1:]
    detail = [panel for panel in layouts["detail"] if panel.get("name") != "lecrownPursuitScoring"]
    detail.append({"name": "lecrownPursuitScoring", "label": "LeCrown AI-first Pursuit Ranking", "rows": [
        [{"name": "cPursuitRank"}, {"name": "cPursuitStatus"}],
        [{"name": "cWinLikelihoodScore"}, {"name": "cProfitabilityPotential"}],
        [{"name": "cStrategicPotential"}, {"name": "cPursuitPriority"}],
        [{"name": "cPursuitConfidence"}, {"name": "cPursuitAssessedAt"}],
        [{"name": "cPursuitAssessment", "fullWidth": True}],
    ]})
    filters = list(layouts["filters"])
    for name in ["cPursuitStatus", "cPursuitRank", "cWinLikelihoodScore", "cProfitabilityPotential", "cStrategicPotential"]:
        if name not in filters:
            filters.append(name)
    for name, layout in [("list", listing), ("detail", detail), ("filters", filters)]:
        client.call("PUT", "/Opportunity/layout/" + name, json=layout)
        if client.call("GET", "/Opportunity/layout/" + name) != layout:
            raise ValueError("Layout did not read back: " + name)


def apply(client, model, plan_file, output, expected_count, configure_fields):
    plan = json.loads(plan_file.read_text())
    if plan["model_hash"] != model_hash(model):
        raise ValueError("Model changed after preview")
    now = datetime.now(timezone.utc)
    if not 0 <= (now - datetime.fromisoformat(plan["created_at"])).total_seconds() <= 7200:
        raise ValueError("Preview must be less than two hours old")
    current = client.opportunities()
    if plan["count"] != expected_count or len(current) != expected_count or set(plan["inputs"]) != {r["id"] for r in current}:
        raise ValueError("CRM record set differs from approved bounded preview")
    for row in current:
        if input_hash(row) != plan["inputs"][row["id"]]:
            raise ValueError("CRM record changed since preview: " + row["id"])
    if set(plan["updates"]) != set(plan["inputs"]):
        raise ValueError("Score updates must cover exactly the previewed IDs")
    for payload in plan["updates"].values():
        if set(payload) != set(SCORE_FIELDS):
            raise ValueError("Refusing a payload outside score fields")
        for field in ["cWinLikelihoodScore", "cProfitabilityPotential", "cStrategicPotential", "cPursuitPriority"]:
            if payload[field] is not None and (type(payload[field]) is not int or not 0 <= payload[field] <= 100):
                raise ValueError("Invalid score value")
    if sorted(payload["cPursuitRank"] for payload in plan["updates"].values()) != list(range(1, expected_count + 1)):
        raise ValueError("Expected unique consecutive pursuit ranks")
    if not (output / "apply-before.json").exists():
        write_private(output / "apply-before.json", current)
    if configure_fields:
        configure(client, output)
    else:
        defs = client.call("GET", "/Metadata")["entityDefs"]["Opportunity"]["fields"]
        if not set(SCORE_FIELDS) <= set(defs):
            raise ValueError("Score fields missing; explicitly configure them first")
    receipts = []
    for original in current:
        record_id = original["id"]
        fresh = client.call("GET", "/Opportunity/" + record_id)
        if input_hash(fresh) != plan["inputs"][record_id]:
            raise ValueError("CRM content changed during apply: " + record_id)
        payload = plan["updates"][record_id]
        if any(fresh.get(key) != value for key, value in payload.items()):
            # Never blindly retry an uncertain PUT. Always reconcile by reading the same record.
            try:
                client.call("PUT", "/Opportunity/" + record_id, json={**payload, "_prev": {key: fresh.get(key) for key in payload}})
            except RuntimeError:
                verified = client.call("GET", "/Opportunity/" + record_id)
                if any(verified.get(key) != value for key, value in payload.items()):
                    raise
        verified = client.call("GET", "/Opportunity/" + record_id)
        if any(verified.get(key) != value for key, value in payload.items()) or input_hash(verified) != plan["inputs"][record_id]:
            raise ValueError("Score or protected business field verification failed: " + record_id)
        receipts.append({"id": record_id, "rank": payload["cPursuitRank"], "verified": True})
        write_private(output / "apply-receipt.json", {"complete": False, "records": receipts})
        print(f"Verified Opportunity {record_id}, rank {payload['cPursuitRank']}", flush=True)
    final = client.opportunities()
    if len(final) != expected_count or {r["id"] for r in final} != set(plan["inputs"]):
        raise ValueError("CRM changed before aggregate verification")
    for row in final:
        if input_hash(row) != plan["inputs"][row["id"]] or any(row.get(k) != v for k,v in plan["updates"][row["id"]].items()):
            raise ValueError("Aggregate verification failed")
    write_private(output / "apply-receipt.json", {"complete": True, "model": model["version"], "verified_count": len(receipts), "records": receipts, "protected_fields_unchanged": True})
    print(json.dumps({"complete": True, "verified_count": len(receipts), "protected_fields_unchanged": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["preview", "apply"])
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=ROOT / "data/crm-pursuit-model.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--refresh-evidence", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--configure-fields", action="store_true")
    args = parser.parse_args()
    model = json.loads(args.model.read_text())
    client = Client(args.env_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "preview":
        preview(client, model, args.output_dir, args.evidence_dir, args.refresh_evidence)
    elif not args.plan or args.expected_count is None:
        parser.error("apply requires --plan and --expected-count; no writes performed")
    else:
        apply(client, model, args.plan, args.output_dir, args.expected_count, args.configure_fields)
