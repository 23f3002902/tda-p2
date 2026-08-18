"""Check whether the Irish preference claim has valid supplier support."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


def pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def first(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def analyze(data_dir: Path) -> dict:
    declaration = pdf_text(data_dir / "declaration 7.pdf")
    invoice = pdf_text(data_dir / "commercial_invoice 7.pdf")
    register = pd.read_csv(
        data_dir / "supplier_origin_register.csv", parse_dates=["valid_from", "valid_to"]
    )
    reference = (data_dir / "supplier_declaration_reference.txt").read_text()
    workshop = (data_dir / "origin-workshop.md").read_text()

    case_date = pd.Timestamp(first(r"Declaration date\s+(\d{4}-\d{2}-\d{2})", declaration))
    product = first(r"\n(P\d+)\s+-", declaration)
    supplier = first(r"for\s+(SUP-\d+)\s*/", reference)
    row = register.loc[
        register["supplier_id"].eq(supplier) & register["product_id"].eq(product)
    ].iloc[0]

    return {
        "case": first(r"Customs Declaration\s+([A-Z]{2}-\d{4}-\d+)", declaration),
        "declaration_date": str(case_date.date()),
        "product_id": product,
        "preference_indicator": first(r"\n(Yes|No)\nDeclaration extract", declaration),
        "declared_origin": first(r"P\d+\s+-[^\n]+\n\d{8}\n([A-Za-z ]+)", declaration).strip(),
        "invoice_manufacturing_country_us": "United States" in invoice,
        "register_supplier": supplier,
        "register_valid_to": str(row["valid_to"].date()),
        "register_status": row["register_status"],
        "days_after_register_expiry": int((case_date - row["valid_to"]).days),
        "reference_says_no_current_document": "no current document reference found" in reference,
        "reference_disclaims_nonexistence": "does not prove" in reference,
        "workshop_requires_declaration_and_rule": (
            "supplier declaration and the rule used for the claim" in workshop
        ),
        "workshop_warns_register_incomplete": "register is not always updated" in workshop,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.data_dir), indent=2))
