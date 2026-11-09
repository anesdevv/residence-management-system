#!/usr/bin/env python3
"""RÉSIVO — i18n Catalog Export Tool.

Exports translation strings from desktop and web JSON catalogs into a unified
CSV file (`docs/i18n-review.csv`) for human translators and institutional QA review.
"""

import csv
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Recursively flatten nested dictionary to dot notation."""
    items: dict[str, str] = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, full_key))
        else:
            items[full_key] = str(v)
    return items


def export_catalogs() -> Path:
    desktop_en_path = REPO_ROOT / "desktop" / "i18n" / "en.json"
    desktop_fr_path = REPO_ROOT / "desktop" / "i18n" / "fr.json"
    web_en_path = REPO_ROOT / "web" / "src" / "i18n" / "en.json"
    web_fr_path = REPO_ROOT / "web" / "src" / "i18n" / "fr.json"

    rows: list[dict[str, str]] = []

    # Desktop
    if desktop_en_path.is_file() and desktop_fr_path.is_file():
        with open(desktop_en_path, "r", encoding="utf-8") as f:
            d_en = flatten_dict(json.load(f))
        with open(desktop_fr_path, "r", encoding="utf-8") as f:
            d_fr = flatten_dict(json.load(f))

        all_keys = sorted(set(d_en.keys()) | set(d_fr.keys()))
        for k in all_keys:
            ns = k.split(".")[0] if "." in k else "common"
            rows.append({
                "platform": "desktop",
                "namespace": ns,
                "key": k,
                "en": d_en.get(k, ""),
                "fr": d_fr.get(k, ""),
            })

    # Web
    if web_en_path.is_file() and web_fr_path.is_file():
        with open(web_en_path, "r", encoding="utf-8") as f:
            w_en = flatten_dict(json.load(f))
        with open(web_fr_path, "r", encoding="utf-8") as f:
            w_fr = flatten_dict(json.load(f))

        all_keys = sorted(set(w_en.keys()) | set(w_fr.keys()))
        for k in all_keys:
            ns = k.split(".")[0] if "." in k else "common"
            rows.append({
                "platform": "web",
                "namespace": ns,
                "key": k,
                "en": w_en.get(k, ""),
                "fr": w_fr.get(k, ""),
            })

    output_csv = REPO_ROOT / "docs" / "i18n-review.csv"
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["platform", "namespace", "key", "en", "fr"])
        writer.writeheader()
        writer.writerows(rows)

    desktop_count = sum(1 for r in rows if r["platform"] == "desktop")
    web_count = sum(1 for r in rows if r["platform"] == "web")
    missing_fr = sum(1 for r in rows if not r["fr"].strip())

    print(f"Exported {len(rows)} entries to {output_csv.relative_to(REPO_ROOT)}")
    print(f"  - Desktop: {desktop_count} keys")
    print(f"  - Web:     {web_count} keys")
    print(f"  - Missing French translations: {missing_fr}")

    return output_csv


if __name__ == "__main__":
    export_catalogs()
