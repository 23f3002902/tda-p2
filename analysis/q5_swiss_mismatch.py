"""Trace the Swiss tariff mismatch across the packet and reference workbooks."""

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
    declaration = pdf_text(data_dir / "declaration.pdf")
    invoice = pdf_text(data_dir / "commercial_invoice.pdf")
    master = pd.read_excel(data_dir / "product_master_current.xlsx", sheet_name="Product Master")
    swiss = pd.read_excel(data_dir / "country_tariff_matrix.xlsx", sheet_name="Swiss Matrix")
    swiss["Effective From"] = pd.to_datetime(swiss["Effective From"])
    swiss["Effective To"] = pd.to_datetime(swiss["Effective To"])

    product = first(r"\n(P\d+)\s+-", declaration)
    declared_code = first(r"P\d+\s+-[^\n]+\n(\d{8})", declaration)
    declaration_date = pd.Timestamp(first(r"Declaration date\s+(\d{4}-\d{2}-\d{2})", declaration))
    master_row = master.loc[master["Product ID"].eq(product)].iloc[0]
    swiss_rows = swiss.loc[
        swiss["Product ID"].eq(product)
        & swiss["Effective From"].le(declaration_date)
        & (swiss["Effective To"].isna() | swiss["Effective To"].ge(declaration_date))
    ]
    swiss_row = swiss_rows.iloc[0]
    schema = (data_dir / "canonical-schema-v0.3.md").read_text()

    return {
        "case": first(r"Customs Declaration\s+([A-Z]{2}-\d{4}-\d+)", declaration),
        "declaration_date": str(declaration_date.date()),
        "product_id": product,
        "declared_swiss_code": declared_code,
        "effective_swiss_matrix_code": str(swiss_row["Approved CN8"]),
        "helios_code": str(master_row["Helios Commodity Code"]),
        "base_hs6": str(master_row["Base HS6"]),
        "same_hs6_prefix": declared_code[:6] == str(master_row["Base HS6"]),
        "invoice_product_match": product in invoice,
        "schema_explicitly_omits_code_system": "code-system identifier" in schema.split("Not yet modeled:", 1)[-1],
        "matrix_authority_type": swiss_row["Authority Type"],
        "matrix_owner_note": swiss_row["Owner Note"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.data_dir), indent=2))
