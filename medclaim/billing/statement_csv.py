"""CSV export of a patient's current statement (T-102).

Reads through the repository layer and deliberately does not call
build_statement(), which has side effects (it writes a statements row) and is
untested. Totals follow docs/domain-primer.md:
balance = charges - adjustments - payments. Voided claims are not on the
current statement (ADR-002), so no row is ever flagged voided; the column is
kept because the export format asks for it.

Money is integer cents internally and formatted as dollars.cents only here.
No patient name, MRN or contact details are written.
"""
from __future__ import annotations

import csv
import io

from medclaim.repo import ClaimRepository


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    dollars, rem = divmod(abs(cents), 100)
    return f"{sign}{dollars}.{rem:02d}"


def export_statement_csv(patient_id: str) -> str:
    repo = ClaimRepository()
    claims = repo.by_patient(patient_id)
    paid = repo.paid_cents_by_claim(patient_id)

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["claim_id", "service_date", "charge", "voided"])
    total_charges = 0
    total_adjustments = 0
    total_payments = 0
    for c in claims:
        total_charges += c["amount_cents"]
        total_adjustments += c["adjustment_cents"] or 0
        total_payments += paid.get(c["id"], 0)
        writer.writerow([
            c["id"],
            c["service_date"],
            format_cents(c["amount_cents"]),
            "true" if c["is_deleted"] == 1 else "false",
        ])
    balance = total_charges - total_adjustments - total_payments

    writer.writerow([])
    writer.writerow(["summary", "amount"])
    writer.writerow(["total_charges", format_cents(total_charges)])
    writer.writerow(["total_adjustments", format_cents(total_adjustments)])
    writer.writerow(["total_payments", format_cents(total_payments)])
    writer.writerow(["balance", format_cents(balance)])
    return out.getvalue()
