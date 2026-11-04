"""Local neural embeddings plus a supervised, rating-trained qualification classifier."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.services.crm_pursuit_sync import write_private
from app.services.opportunity_descriptions import content_hash

MODEL = "BAAI/bge-small-en-v1.5"
VERSION = "lecrown-semantic-fit-v1"
CAPABILITIES = Path(__file__).resolve().parents[1] / "resources/lecrown-capabilities.json"


def state_dir():
    return Path(get_settings().semantic_fit_state_dir)


def labels(snapshot):
    return {entry["candidate"]["source_key"]: entry.get("fit_feedback", {})
            for entry in snapshot.get("candidates", {}).values()
            if entry.get("fit_feedback", {}).get("rating") in {"high", "low"}}


def label_hash(snapshot):
    values = {key: [item.get("rating"), item.get("version")] for key, item in labels(snapshot).items()}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def chunks(text, tokenizer, size=400):
    # Count actual model tokens, and disable truncation so the tail is never discarded.
    tokenizer.no_truncation()
    offsets = [(start, end) for start, end in tokenizer.encode(text, add_special_tokens=False).offsets if end > start]
    return [text[offsets[start][0]:offsets[min(start + size, len(offsets)) - 1][1]]
            for start in range(0, len(offsets), size)] or [text or "Unknown scope"]


class Encoder:
    def __init__(self, directory, offline=True):
        from fastembed import TextEmbedding
        self.model = TextEmbedding(model_name=MODEL, cache_dir=os.getenv("SEMANTIC_MODEL_CACHE", "/opt/lecrown-models"),
                                   threads=2, local_files_only=offline)
        artifact = hashlib.sha256()
        root = Path(os.getenv("SEMANTIC_MODEL_CACHE", "/opt/lecrown-models"))
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".onnx", ".json", ".txt"}:
                artifact.update(str(path.relative_to(root)).encode())
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        artifact.update(block)
        self.artifact_hash = artifact.hexdigest()
        self.tokenizer = self.model.model.tokenizer
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.cache = sqlite3.connect(directory / "embeddings.db")
        os.chmod(directory / "embeddings.db", 0o600)
        self.cache.execute("CREATE TABLE IF NOT EXISTS embeddings (hash TEXT PRIMARY KEY, vector TEXT NOT NULL, chunks INTEGER NOT NULL)")

    def encode(self, texts):
        import numpy as np
        vectors = []
        for text in texts:
            key = hashlib.sha256((VERSION + MODEL + self.artifact_hash + text).encode()).hexdigest()
            row = self.cache.execute("SELECT vector FROM embeddings WHERE hash=?", (key,)).fetchone()
            if row:
                vector = np.array(json.loads(row[0]))
            else:
                pieces = chunks(text, self.tokenizer)
                # Length-weighted pooling covers the entire description, not its first window.
                embedded = list(self.model.embed(pieces, batch_size=16))
                vector = np.average(embedded, axis=0, weights=[max(1, len(p)) for p in pieces])
                vector /= max(float(np.linalg.norm(vector)), 1e-12)
                self.cache.execute("INSERT OR REPLACE INTO embeddings VALUES (?,?,?)", (key, json.dumps(vector.tolist()), len(pieces)))
                self.cache.commit()
            vectors.append(vector)
        return np.array(vectors)


def fit_classifier(vectors, targets, groups):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.metrics import precision_score, recall_score
    if min(sum(targets), len(targets) - sum(targets)) < 10:
        return None, {"ready": False, "reason": "At least ten High and ten Low examples are required."}
    if len(set(groups)) < 5:
        return None, {"ready": False, "reason": "At least five independent scope groups are required."}
    targets = np.array(targets)
    predictions = np.zeros(len(targets))
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=37)
    for train, test in splitter.split(vectors, targets, groups):
        if len(set(targets[train])) != 2:
            return None, {"ready": False, "reason": "Insufficient independent groups for validation."}
        estimator = LogisticRegression(C=4, class_weight="balanced", max_iter=1000, random_state=37)
        estimator.fit(vectors[train], targets[train])
        predictions[test] = estimator.predict_proba(vectors[test])[:, 1]
    threshold = 1.01
    for value in np.arange(.65, 1, .025):
        selected = predictions >= value
        if sum(selected) >= 5 and precision_score(targets, selected, zero_division=0) >= .9:
            threshold = round(float(value), 3)
            break
    classifier = LogisticRegression(C=4, class_weight="balanced", max_iter=1000, random_state=37).fit(vectors, targets)
    positive = predictions >= threshold
    return classifier, {"ready": True, "validation": "five-fold grouped out-of-fold; diagnostic, not a guarantee",
                        "high_threshold": threshold, "precision": round(float(precision_score(targets, positive, zero_division=0)), 3),
                        "recall": round(float(recall_score(targets, positive, zero_division=0)), 3),
                        "evaluated": len(targets), "automatic_positive_enabled": threshold <= 1}


def group_key(row):
    value = re.sub(r"\b(?:draft|similar|pre.solicitation|meeting)\b|\d+", " ", row["title"].casefold())
    return " ".join(re.findall(r"[a-z]+", value))


def build_projection(records, snapshot, encoder):
    import numpy as np
    rated = labels(snapshot)
    capabilities = json.loads(CAPABILITIES.read_text())
    source_texts = [r["title"] + "\n\n" + (r.get("description_text") or "") for r in records]
    vectors = encoder.encode(source_texts)
    allowed = list(capabilities["in_scope"])
    excluded = list(capabilities["out_of_scope"])
    prototypes = encoder.encode([*capabilities["in_scope"].values(), *capabilities["out_of_scope"].values()])
    indexes = [i for i, row in enumerate(records) if row["source_key"] in rated]
    targets = [int(rated[records[i]["source_key"]]["rating"] == "high") for i in indexes]
    classifier, evaluation = fit_classifier(vectors[indexes], targets, [group_key(records[i]) for i in indexes])
    probabilities = classifier.predict_proba(vectors)[:, 1] if classifier else np.full(len(records), .5)
    output = {}
    for i, row in enumerate(records):
        affinities = prototypes @ vectors[i]
        good = int(np.argmax(affinities[:len(allowed)]))
        bad = int(np.argmax(affinities[len(allowed):])) + len(allowed)
        margin = float(affinities[good] - affinities[bad])
        scope_ok = margin >= .015 and float(affinities[good]) >= .38
        description = row.get("description_text") or ""
        available = len(description.split()) >= 12 and description.casefold().strip() != row["title"].casefold().strip()
        staffing = bool(re.search(r"24\s*/\s*7|24x7|staff augmentation|dedicated on.site staff|full.time equivalents", description, re.I))
        qualified, basis = False, "semantic_review"
        reason = "Semantic evidence is inconclusive; review the full scope."
        if not available:
            basis, reason = "needs_description", "A substantive source description is missing; title-only records are not automatically qualified."
        elif not scope_ok:
            basis, reason = "semantic_out_of_scope", "Full scope is not sufficiently aligned with LeCrown's IT/AI/data or new-energy integration capabilities."
        elif staffing:
            basis, reason = "delivery_review", "Review mandatory staffing/continuous coverage against founder-led, AI-built delivery before qualifying."
        elif classifier and probabilities[i] >= evaluation["high_threshold"]:
            qualified, basis, reason = True, "semantic_high", "Full-description semantic fit and the classifier trained on your ratings support qualification."
        elif classifier and probabilities[i] <= .2:
            basis, reason = "semantic_low", "The rating-trained semantic classifier favors Low fit."
        neighbors = sorted((j for j in indexes if j != i), key=lambda j: -float(vectors[j] @ vectors[i]))[:5]
        examples = [{"source_key": records[j]["source_key"], "title": records[j]["title"],
                     "rating": rated[records[j]["source_key"]]["rating"], "similarity": round(float(vectors[j] @ vectors[i]), 3)} for j in neighbors]
        output[row["source_key"]] = {"content_hash": content_hash(row), "qualified": qualified, "basis": basis,
             "reason": reason, "score": round(float(probabilities[i]) * 100), "capability": allowed[good],
             "scope_margin": round(margin, 4), "description_available": available, "examples": examples}
    return {"version": VERSION, "embedding_model": MODEL, "embedding_artifact_hash": getattr(encoder, "artifact_hash", "test"), "capability_version": capabilities["version"],
            "label_hash": label_hash(snapshot), "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_count": len(indexes), "high_count": sum(targets), "low_count": len(targets) - sum(targets),
            "evaluation": evaluation, "description_count": sum(x["description_available"] for x in output.values()),
            "candidate_count": len(records), "records": output}


class SemanticProjection:
    def __init__(self, snapshot):
        self.expected = label_hash(snapshot)
        path = state_dir() / "projection.json"
        try:
            self.data = json.loads(path.read_text()) if path.exists() else {}
        except (ValueError, OSError):
            self.data = {}
        self.current = self.data.get("version") == VERSION and self.data.get("label_hash") == self.expected

    @property
    def summary(self):
        return {**{k: v for k, v in self.data.items() if k != "records"}, "current": self.current, "enabled": True}

    def apply(self, candidate, feedback):
        data = self.data.get("records", {}).get(candidate.source_key, {})
        current = self.current and data.get("content_hash") == content_hash(candidate.model_dump())
        rating = feedback.get("rating")
        qualified = data.get("qualified", False) if current else False
        basis = data.get("basis", "semantic_pending") if current else "semantic_pending"
        reason = data.get("reason", "") if current else "Waiting for semantic assessment of the current description and ratings."
        categories = candidate.keyword_opportunity_categories or candidate.opportunity_categories
        if rating in {"high", "low"}:
            qualified = rating == "high"
            basis = "human_high" if qualified else "human_low"
            reason = "Your explicit rating is authoritative for this lead."
        if qualified:
            categories = ["it_services"]
        score = data.get("score", 0) if current else 0
        priority = 100 if rating == "high" else 0 if rating == "low" else score if qualified else min(score, 49)
        return type(candidate).model_validate({**candidate.model_dump(), "qualification_match": qualified, "qualification_basis": basis,
            "qualification_reason": reason, "keyword_opportunity_categories": candidate.keyword_opportunity_categories or candidate.opportunity_categories,
            "opportunity_categories": categories, "category_basis": "human_high" if rating == "high" else "semantic" if qualified else "keyword",
            "fit_feedback_rating": rating, "fit_feedback_version": feedback.get("version", 0),
            "fit_feedback_at": feedback.get("reviewed_at"), "fit_feedback_by": feedback.get("reviewed_by"),
            "review_priority_score": priority, "feedback_adjustment": priority - candidate.priority_score,
            "feedback_examples": data.get("examples", []) if current and rating is None else [],
            "semantic_score": score if current else None, "semantic_capability": data.get("capability") if current else None,
            "semantic_model_version": VERSION if current else None})
