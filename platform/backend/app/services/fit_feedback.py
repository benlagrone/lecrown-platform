"""Explainable learned qualification, separate from immutable keyword evidence."""
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
project projects implementation solution solutions program programs annual initial phase
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
        keyword_categories = (candidate.keyword_opportunity_categories
                              if candidate.keyword_opportunity_categories is not None
                              else candidate.opportunity_categories)
        examples = []
        adjustment = 0
        qualified = candidate.is_match
        basis = "keyword"
        reason = "IT keyword evidence meets the threshold." if qualified else "No qualifying IT keyword evidence yet."
        physical_only = "property_services" in keyword_categories and "it_services" not in keyword_categories
        # Human labels train selection, but unreviewed physical-only work still needs direct review.
        if rating is None and not physical_only:
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
                strong = [example for example in examples if example["similarity"] >= 0.5]
                if strong:
                    evidence = sum(example["similarity"] for example in strong)
                    consensus = sum((1 if example["rating"] == "high" else -1) * example["similarity"]
                                    for example in strong) / evidence
                    if abs(consensus) >= 0.6:
                        qualified = consensus > 0
                        basis = "learned_high" if qualified else "learned_low"
                        reason = ("Included" if qualified else "Excluded") + " by similar titles you rated."
        if physical_only:
            qualified, basis = False, "out_of_scope"
            reason = "Physical-work scope stays outside automatic IT qualification."
        if rating in {"high", "low"}:
            qualified = rating == "high"
            basis = "human_high" if qualified else "human_low"
            reason = ("Included as IT and adjacent by your High fit rating." if qualified
                      else "Excluded by your Low fit rating.")
        priority = 100 if rating == "high" else 0 if rating == "low" else max(
            0, min(99, candidate.priority_score + adjustment))
        return GovContractOpportunityRead.model_validate({
            **candidate.model_dump(),
            "keyword_opportunity_categories": keyword_categories,
            "opportunity_categories": ["it_services"] if rating == "high" else keyword_categories,
            "category_basis": "human_high" if rating == "high" else "keyword",
            "fit_feedback_rating": rating,
            "fit_feedback_version": feedback.get("version", 0),
            "fit_feedback_at": feedback.get("reviewed_at"),
            "fit_feedback_by": feedback.get("reviewed_by"),
            "feedback_adjustment": adjustment,
            "feedback_examples": examples,
            "review_priority_score": priority,
            "qualification_match": qualified,
            "qualification_basis": basis,
            "qualification_reason": reason,
        })
