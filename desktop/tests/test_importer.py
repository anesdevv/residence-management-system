import csv
import os
from app.importers.official_list import read_official_file


def test_read_csv(tmp_path):
    path = tmp_path / "list.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["card_id", "first_name", "last_name", "birth_date", "gender", "university", "faculty"])
        w.writerow(["20230001", "Yacine", "Benali", "2003-05-14", "male", "UBB", "Sciences"])
        w.writerow(["", "Ignored", "Row", "", "", "", ""])
    rows = read_official_file(str(path))
    assert len(rows) == 1
    assert rows[0]["card_id"] == "20230001"
    assert rows[0]["gender"] == "male"


def test_read_csv_normalized_headers(tmp_path):
    path = tmp_path / "custom_headers.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Card ID", "First Name", "Last Name", "Birth Date", "Gender", "University", "Faculty"])
        w.writerow(["20230099", "Sara", "Amrani", "2004-01-15", "Female", "UBB", "Technology"])
    rows = read_official_file(str(path))
    assert len(rows) == 1
    assert rows[0]["card_id"] == "20230099"
    assert rows[0]["first_name"] == "Sara"
    assert rows[0]["gender"] == "female"
    assert rows[0]["birth_date"] == "2004-01-15"

