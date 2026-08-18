"""Test whether the QC extract can support a routine-release KPI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def analyze(data_dir: Path) -> dict:
    releases = pd.read_csv(
        data_dir / "batch_release.csv",
        parse_dates=["receipt_ts", "lab_complete_ts", "qcore_release_ts", "source_snapshot_ts"],
    )
    freshness = pd.read_csv(data_dir / "source_freshness.csv")
    released = releases.loc[releases["disposition"].eq("RELEASED")].copy()
    released["receipt_to_release_h"] = (
        released["qcore_release_ts"] - released["receipt_ts"]
    ).dt.total_seconds() / 3600
    released["lab_to_release_h"] = (
        released["qcore_release_ts"] - released["lab_complete_ts"]
    ).dt.total_seconds() / 3600
    routine_proxy = released.loc[
        released["coa_status"].eq("AVAILABLE")
        & ~released["open_deviation"]
        & ~released["market_spec_override"]
    ]
    at_snapshot_time = released["qcore_release_ts"].dt.strftime("%H:%M:%S").eq("02:10:00")
    incomplete_evidence = ~released["coa_status"].eq("AVAILABLE")

    return {
        "rows": len(releases),
        "released_rows": len(released),
        "released_receipt_to_release_median_h": round(released["receipt_to_release_h"].median(), 3),
        "released_lab_to_release_median_h": round(released["lab_to_release_h"].median(), 3),
        "routine_proxy_rows": len(routine_proxy),
        "routine_proxy_receipt_to_release_median_h": round(routine_proxy["receipt_to_release_h"].median(), 3),
        "routine_proxy_lab_to_release_median_h": round(routine_proxy["lab_to_release_h"].median(), 3),
        "routine_proxy_within_24h_from_lab_pct": round(100 * routine_proxy["lab_to_release_h"].le(24).mean(), 2),
        "released_at_02_10": int(at_snapshot_time.sum()),
        "released_at_02_10_pct": round(100 * at_snapshot_time.mean(), 2),
        "released_with_missing_or_pending_coa": int(incomplete_evidence.sum()),
        "released_with_missing_or_pending_coa_pct": round(100 * incomplete_evidence.mean(), 2),
        "released_with_open_deviation": int(released["open_deviation"].sum()),
        "released_with_market_override": int(released["market_spec_override"].sum()),
        "freshness": freshness.set_index("source")["snapshot_ts"].to_dict(),
        "missing_required_fields": [
            "required_evidence_available_ts",
            "service_class",
            "exception_resolved_ts",
            "authorized_disposition_event_ts",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.data_dir), indent=2))
