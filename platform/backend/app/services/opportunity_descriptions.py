"""Preserve complete source descriptions and explicitly distinguish missing scope."""
from __future__ import annotations

import hashlib
import re
from bs4 import BeautifulSoup

TEXT_KEYS = ("description", "project_description", "statement_of_work", "StatementOfWork", "scope_of_work", "summary_description", "body")


def plain(value):
    if not isinstance(value, str):
        return ""
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True) if "<" in value else value.strip()


def description_fields(record):
    raw = record.raw_payload or {}
    captured = raw.get("qualification_description") or {}
    pieces = []
    for value in [captured.get("text"), *[raw.get(key) for key in TEXT_KEYS]]:
        text = plain(value)
        if text and text.casefold() != (record.title or "").strip().casefold() and text not in pieces:
            pieces.append(text)
    text = "\n\n".join(pieces)
    status = "available" if len(text.split()) >= 12 else "brief" if text else captured.get("status", "missing")
    if not text and status == "available":
        status = "title_only"
    return {"description_text": text, "description_status": status,
            "description_url": captured.get("url") or record.source_url,
            "description_checked_at": captured.get("checked_at")}


def content_hash(candidate):
    return hashlib.sha256((str(candidate.get("title") or "") + "\n" + str(candidate.get("description_text") or "")).encode()).hexdigest()


def preserve_description(previous, incoming, source_url):
    captured = (previous or {}).get("qualification_description")
    if captured and captured.get("url") == source_url:
        return {**incoming, "qualification_description": captured}
    return incoming


def public_bonfire_url(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return (parsed.scheme == "https" and bool(re.fullmatch(r"[a-z0-9-]+\.bonfirehub\.com", parsed.hostname or ""))
            and parsed.port is None and not parsed.username and not parsed.password
            and bool(re.fullmatch(r"/opportunities/\d+/?", parsed.path)) and not parsed.query and not parsed.fragment)


def parse_bonfire_description(html):
    soup = BeautifulSoup(html, "html.parser")
    section = soup.select_one("#opportunityMetaSection, .opportunityMetaSection")
    if section is None:
        return ""
    label = next((item for item in section.select("b, strong") if item.get_text(strip=True) == "Project Description:"), None)
    if label is not None:
        scope = label.parent.select_one(".bfMarkdown, .markdown_formatted")
        if scope:
            return scope.get_text("\n", strip=True)
    text = section.get_text("\n", strip=True)
    match = re.search(r"Project Description:\s*(.*)", text, re.S)
    return match.group(1).strip() if match else ""
