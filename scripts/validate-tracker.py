"""Validate tracker CSV structure and the offline browser snapshot."""

import csv
import json
import re
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    tables = {}
    for path in sorted((root / "data").glob("*.csv")):
        with path.open(newline="", encoding="utf-8-sig") as source:
            rows = list(csv.reader(source))
        if not rows or len(set(rows[0])) != len(rows[0]):
            raise ValueError(f"{path.name}: missing or duplicate headers")
        for line, row in enumerate(rows[1:], start=2):
            if len(row) != len(rows[0]):
                raise ValueError(f"{path.name}:{line}: incorrect number of fields")
        tables[f"data/{path.name}"] = [dict(zip(rows[0], row)) for row in rows[1:]]

    html = (root / "tracker/index.html").read_text()
    views = re.findall(r'(\w+):\s*\{\s*title: "[^"]+",\s*file: "\.\./([^"]+)"', html)
    if len(views) != 6:
        raise ValueError("Expected six tracker views; update validation when adding views")
    snapshot = (root / "tracker/data-snapshot.js").read_text()
    snapshot = json.loads(snapshot.removeprefix("window.TRACKER_DATA = ").strip().removesuffix(";"))
    for key, file in views:
        if snapshot.get(key) != tables[file]:
            raise ValueError(f"{key}: offline snapshot differs from {file}")
    print(f"Validated {len(tables)} CSV files and {len(views)} offline tracker views.")


if __name__ == "__main__":
    main()
