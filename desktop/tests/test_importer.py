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


def test_read_xlsx_and_empty_sheet(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Card ID", "First Name", "Last Name", "Birth Date", "Gender", "University", "Faculty"])
    ws.append(["20230555", "Amine", "Kader", "15/03/2002", "Homme", "UBB", "Informatique"])
    path = tmp_path / "test.xlsx"
    wb.save(str(path))
    wb.close()

    rows = read_official_file(str(path))
    assert len(rows) == 1
    assert rows[0]["card_id"] == "20230555"
    assert rows[0]["gender"] == "male"
    assert rows[0]["birth_date"] == "2002-03-15"


def test_read_empty_xlsx(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    path = tmp_path / "empty.xlsx"
    wb.save(str(path))
    wb.close()

    rows = read_official_file(str(path))
    assert rows == []


def test_gender_and_date_variations(tmp_path):
    path = tmp_path / "gender_date.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["card_id", "first_name", "last_name", "birth_date", "gender"])
        w.writerow(["C01", "A", "B", "25-12-2000", "Femme"])
        w.writerow(["C02", "C", "D", "2001/04/10", "m"])
        w.writerow(["C03", "E", "F", "2002-06-01", "f"])
    rows = read_official_file(str(path))
    assert len(rows) == 3
    assert rows[0]["gender"] == "female"
    assert rows[0]["birth_date"] == "2000-12-25"
    assert rows[1]["gender"] == "male"
    assert rows[1]["birth_date"] == "2001-04-10"
    assert rows[2]["gender"] == "female"
    assert rows[2]["birth_date"] == "2002-06-01"


