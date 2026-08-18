"""Generate conservative cross-site spare-part candidates and value classes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ALIASES = {
    "servo": "MTR-4401",
    "hepa": "FLT-1199",
    "belt": "BLT-7302",
    "valve": "VLV-3722",
    "sensor": "SNS-9910",
    "pump seal": "PMP-2288",
    "spindle": "BRG-1507",
    "remote io": "PLC-8840",
}


def infer_mpn(row: pd.Series) -> tuple[str | None, str]:
    if pd.notna(row["manufacturer_part_no"]):
        return row["manufacturer_part_no"], "provided"
    description = row["requested_description"].lower().replace("-", " ")
    for phrase, mpn in ALIASES.items():
        if phrase in description:
            return mpn, "semantic"
    return None, "unmatched"


def analyze(data_dir: Path) -> dict:
    requests = pd.read_csv(data_dir / "part_requests.csv")
    parts = pd.read_csv(data_dir / "spare_parts.csv").merge(
        pd.read_csv(data_dir / "part_restrictions.csv"), on="part_id", validate="one_to_one"
    )
    freshness = pd.read_csv(data_dir / "source_freshness.csv").set_index("source")

    rows = []
    for _, request in requests.iterrows():
        mpn, basis = infer_mpn(request)
        family = parts.loc[
            parts["manufacturer_part_no"].eq(mpn) & parts["site"].ne(request["request_site"])
        ]
        exact = family.loc[
            family["revision"].eq(request["revision_required"])
            & family["uom"].eq(request["uom"])
        ]
        apparently_free = exact.loc[
            exact["available_qty_global"].gt(0) & ~exact["reserved_for_critical_asset"]
        ]
        enough = apparently_free["available_qty_global"].sum() >= request["qty"]
        category = "needs engineering check" if enough else "not transferable"
        rows.append(
            {
                "request_id": request["request_id"],
                "match_basis": basis,
                "inferred_mpn": mpn,
                "candidate_part_ids": exact["part_id"].tolist(),
                "apparently_free_part_ids": apparently_free["part_id"].tolist(),
                "apparently_free_qty": int(apparently_free["available_qty_global"].sum()),
                "requested_qty": int(request["qty"]),
                "external_quote_usd": float(request["external_quote_usd"]),
                "category": category,
            }
        )

    matches = pd.DataFrame(rows)
    total = matches["external_quote_usd"].sum()
    value_by_class = matches.groupby("category")["external_quote_usd"].agg(["count", "sum"])
    summary = {
        category: {
            "requests": int(row["count"]),
            "value_usd": round(float(row["sum"]), 2),
            "value_pct": round(100 * float(row["sum"]) / total, 2),
        }
        for category, row in value_by_class.iterrows()
    }
    summary["actionable now"] = {"requests": 0, "value_usd": 0.0, "value_pct": 0.0}

    return {
        "request_count": len(requests),
        "total_external_quote_usd": round(float(total), 2),
        "classification": summary,
        "maintstar_global_snapshot": freshness.loc["MaintStar-global", "snapshot_ts"],
        "restrictions_status_date": str(parts["local_status_as_of"].max()),
        "matches": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.data_dir), indent=2))
