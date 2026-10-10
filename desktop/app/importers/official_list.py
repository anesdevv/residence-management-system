import csv
from openpyxl import load_workbook

COLUMNS = ["card_id", "first_name", "last_name", "birth_date", "gender", "university", "faculty"]


def read_official_file(path: str) -> list[dict]:
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    else:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        header = [str(c.value).strip() if c.value is not None else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            rows.append({header[i]: row[i] for i in range(min(len(header), len(row)))})

    cleaned: list[dict] = []
    for r in rows:
        card = str(r.get("card_id") or "").strip()
        if not card:
            continue
        cleaned.append({
            "card_id": card,
            "first_name": str(r.get("first_name") or "").strip(),
            "last_name": str(r.get("last_name") or "").strip(),
            "birth_date": str(r.get("birth_date") or "").strip() or None,
            "gender": (str(r.get("gender") or "").strip().lower() or None),
            "university": str(r.get("university") or "").strip() or None,
            "faculty": str(r.get("faculty") or "").strip() or None,
        })
    return cleaned
