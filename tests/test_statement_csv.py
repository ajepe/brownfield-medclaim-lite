import csv
import io

from fastapi.testclient import TestClient

from medclaim.api import app
from medclaim.billing.statement import build_statement
from medclaim.billing.statement_csv import export_statement_csv, format_cents
from medclaim.claims import void_claim


def _rows(text):
    return list(csv.reader(io.StringIO(text)))


def _summary(text):
    rows = _rows(text)
    return {r[0]: r[1] for r in rows[rows.index(["summary", "amount"]) + 1:]}


def test_format_cents():
    assert format_cents(0) == "0.00"
    assert format_cents(5) == "0.05"
    assert format_cents(12_345) == "123.45"
    assert format_cents(-250) == "-2.50"


def test_csv_lines_and_totals(client, seed):
    seed.claims(patient_id="P-2001",
                amounts_cents=[12_500, 8_000, 30_000], adjusted=[0, 800, 0])
    rows = _rows(export_statement_csv("P-2001"))
    assert rows[0] == ["claim_id", "service_date", "charge", "voided"]
    assert [r[2] for r in rows[1:4]] == ["125.00", "80.00", "300.00"]
    assert all(r[3] == "false" for r in rows[1:4])
    summary = _summary(export_statement_csv("P-2001"))
    assert summary == {"total_charges": "505.00", "total_adjustments": "8.00",
                       "total_payments": "0.00", "balance": "497.00"}


def test_csv_excludes_voided_and_matches_statement(client, seed):
    keep = seed.claim(patient_id="P-2001", amount_cents=10_000, adjustment_cents=100)
    gone = seed.claim(patient_id="P-2001", amount_cents=7_777)
    void_claim(gone.id, reason="duplicate")
    text = export_statement_csv("P-2001")
    assert gone.id not in text
    assert keep.id in text
    stmt = build_statement("P-2001")
    summary = _summary(text)
    assert summary["balance"] == format_cents(stmt.balance_cents)
    assert summary["total_charges"] == format_cents(stmt.total_charges_cents)


def test_csv_subtracts_payments_and_never_leaks_pii(client):
    text = export_statement_csv("P-1042")
    summary = _summary(text)
    assert summary["total_charges"] == "315.00"
    assert summary["balance"] == "310.00"
    assert "Margaret" not in text and "MRN" not in text
    stmt = build_statement("P-1042")
    assert summary["balance"] == format_cents(stmt.balance_cents)


def test_csv_endpoint(client):
    c = TestClient(app)
    r = c.get("/patients/P-1042/statement.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert c.get("/patients/NOPE/statement.csv").status_code == 404
