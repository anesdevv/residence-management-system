import csv
from datetime import date, datetime
from openpyxl import load_workbook

COLUMNS = ["card_id", "first_name", "last_name", "birth_date", "gender", "university", "faculty"]


def read_official_file(path: str) -> list[dict]:
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as fh:
            raw_rows = list(csv.DictReader(fh))
    else:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        header = [str(c.value).strip() if c.value is not None else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
        raw_rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            raw_rows.append({header[i]: row[i] for i in range(min(len(header), len(row)))})

    cleaned: list[dict] = []
    for raw in raw_rows:
        r = {str(k).strip().lower().replace(" ", "_"): v for k, v in raw.items() if k}
        card = str(r.get("card_id") or "").strip()
        if not card:
            continue

        b = r.get("birth_date")
        if isinstance(b, (date, datetime)):
            birth_date = b.strftime("%Y-%m-%d")
        else:
            birth_date = str(b or "").strip() or None

        gender_val = str(r.get("gender") or "").strip().lower() or None

        cleaned.append({
            "card_id": card,
            "first_name": str(r.get("first_name") or "").strip(),
            "last_name": str(r.get("last_name") or "").strip(),
            "birth_date": birth_date,
            "gender": gender_val,
            "university": str(r.get("university") or "").strip() or None,
            "faculty": str(r.get("faculty") or "").strip() or None,
        })
    return cleaned

