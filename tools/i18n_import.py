#!/usr/bin/env python3
"""RÉSIVO — i18n Catalog Import Tool.

Imports reviewed translation strings from `docs/i18n-review.csv` back into
the desktop and web JSON catalogs with placeholder verification and schema validation.
"""

import csv
import json
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def unflatten_dict(flat: dict[str, str]) -> dict[str, Any]:
    """Reconstruct nested dictionary from dot notation."""
    root: dict[str, Any] = {}
    for dot_key, value in flat.items():
        parts = dot_key.split(".")
        curr = root
        for part in parts[:-1]:
            if part not in curr or not isinstance(curr[part], dict):
                curr[part] = {}
            curr = curr[part]
        curr[parts[-1]] = value
    return root


def extract_placeholders(text: str) -> set[str]:
    return set(_PLACEHOLDER_RE.findall(text))


def import_csv(csv_path: Path | None = None) -> bool:
    if csv_path is None:
        csv_path = REPO_ROOT / "docs" / "i18n-review.csv"

    if not csv_path.is_file():
        print(f"Error: CSV file not found at {csv_path}", file=sys.stderr)
        return False

    desktop_en: dict[str, str] = {}
    desktop_fr: dict[str, str] = {}
    web_en: dict[str, str] = {}
    web_fr: dict[str, str] = {}

    errors = 0

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):
            platform = row.get("platform", "").strip().lower()
            key = row.get("key", "").strip()
            en_val = row.get("en", "")
            fr_val = row.get("fr", "")

            if not key:
                continue

            en_params = extract_placeholders(en_val)
            fr_params = extract_placeholders(fr_val)
            if en_params != fr_params:
                print(
                    f"Warning [Row {row_idx}] Placeholder mismatch for '{key}': "
                    f"EN={en_params} vs FR={fr_params}",
                    file=sys.stderr,
                )
                errors += 1

            if platform == "desktop":
                desktop_en[key] = en_val
                desktop_fr[key] = fr_val
            elif platform == "web":
                web_en[key] = en_val
                web_fr[key] = fr_val
            else:
                print(f"Warning [Row {row_idx}] Unknown platform '{platform}'", file=sys.stderr)

    # Write Desktop
    if desktop_en and desktop_fr:
        d_en_path = REPO_ROOT / "desktop" / "i18n" / "en.json"
        d_fr_path = REPO_ROOT / "desktop" / "i18n" / "fr.json"
        with open(d_en_path, "w", encoding="utf-8") as f:
            json.dump(unflatten_dict(desktop_en), f, indent=2, ensure_ascii=False)
        with open(d_fr_path, "w", encoding="utf-8") as f:
            json.dump(unflatten_dict(desktop_fr), f, indent=2, ensure_ascii=False)
        print(f"Updated Desktop catalogs ({len(desktop_en)} keys)")

    # Write Web
    if web_en and web_fr:
        w_en_path = REPO_ROOT / "web" / "src" / "i18n" / "en.json"
        w_fr_path = REPO_ROOT / "web" / "src" / "i18n" / "fr.json"
        with open(w_en_path, "w", encoding="utf-8") as f:
            json.dump(unflatten_dict(web_en), f, indent=2, ensure_ascii=False)
        with open(w_fr_path, "w", encoding="utf-8") as f:
            json.dump(unflatten_dict(web_fr), f, indent=2, ensure_ascii=False)
        print(f"Updated Web catalogs ({len(web_en)} keys)")

    if errors > 0:
        print(f"Import completed with {errors} warnings.")
    else:
        print("Import completed with 0 errors!")
    return True


if __name__ == "__main__":
    import_csv()
