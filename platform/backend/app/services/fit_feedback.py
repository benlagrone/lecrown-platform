"""Explainable example-based ranking; human ratings never rewrite source evidence."""
from __future__ import annotations

import re
import unicodedata

from app.schemas.gov_contract import GovContractOpportunityRead
from app.services import candidate_inbox


STOP_WORDS = frozenset("""
the and for with from that this into during through requested request requests proposals
proposal qualifications qualification quote quotes bid bids rebid rfp rfq rfi itb ifb
services service professional expert performance contract contracts term year years
county city state university district school public department authority port basis open
provide providing procurement purchase purchasing supply supplies renewal agreement
solicitation number requested including related requirements support management system systems
""".split())


def _tokens(candidate: dict) -> frozenset[str]:
    title = unicodedata.normalize("NFKC", str(candidate.get("title") or "")).casefold()
    return frozenset(word for word in re.findall(r"[a-z][a-z0-9]+", title)
                     if word not in STOP_WORDS and not any(char.isdigit() for char in word))


class FeedbackRanker:
    def __init__(self, snapshot: dict):
        self.entries = {entry["candidate"]["source_key"]: entry
                        for entry in snapshot.get("candidates", {}).values()}
        self.examples = []
        self.counts = {"high": 0, "low": 0, "unreviewed": 0, "all": len(self.entries)}
        for key, entry in self.entries.items():
            rating = entry.get("fit_feedback", {}).get("rating")
            self.counts[rating if rating in {"high", "low"} else "unreviewed"] += 1
            if rating in {"high", "low"}:
                self.examples.append((key, rating, _tokens(entry["candidate"]), entry["candidate"]["title"]))

    @classmethod
    def load(cls):
        return cls(candidate_inbox.snapshot() if candidate_inbox.configured() else {})

    def apply(self, candidate: GovContractOpportunityRead) -> GovContractOpportunityRead:
        entry = self.entries.get(candidate.source_key, {})
        feedback = entry.get("fit_feedback", {})
        rating = feedback.get("rating")
        examples = []
        adjustment = 0
        # Out-of-scope records can be labeled, but cannot teach the automatic IT gate to disappear.
        if rating is None and "it_services" in candidate.opportunity_categories:
            tokens = _tokens({"title": candidate.title})
            for key, label, other_tokens, title in self.examples:
                if key == candidate.source_key:
                    continue
                overlap = tokens & other_tokens
                similarity = len(overlap) / len(tokens | other_tokens) if tokens | other_tokens else 0
                if len(overlap) >= 2 and similarity >= 0.25:
                    examples.append({"source_key": key, "title": title, "rating": label,
                                     "similarity": round(similarity, 3)})
            examples.sort(key=lambda example: (-example["similarity"], example["source_key"]))
            examples = examples[:5]
            if examples:
                signed = sum((1 if example["rating"] == "high" else -1) * example["similarity"]
                             for example in examples)
                adjustment = round(20 * signed / len(examples))
        priority = 100 if rating == "high" else 0 if rating == "low" else max(
            0, min(99, candidate.priority_score + adjustment))
        return GovContractOpportunityRead.model_validate({
            **candidate.model_dump(),
            "fit_feedback_rating": rating,
            "fit_feedback_version": feedback.get("version", 0),
            "fit_feedback_at": feedback.get("reviewed_at"),
            "fit_feedback_by": feedback.get("reviewed_by"),
            "feedback_adjustment": adjustment,
            "feedback_examples": examples,
            "review_priority_score": priority,
        })
