"""Reconcile the flagged May 31 dealer recharge cluster."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


FLAG_DATE = pd.Timestamp("2026-05-31")
FLAG_DEALERS = {"DLR-104", "DLR-219"}


def analyze(data_dir: Path) -> dict:
    recharge = pd.read_csv(
        data_dir / "recharges.csv",
        parse_dates=["effective_event_date", "posted_at"],
    )
    imports = pd.read_csv(data_dir / "dealer_import_log.csv", parse_dates=["posted_at"])

    flagged = recharge[
        recharge["posted_at"].dt.normalize().eq(FLAG_DATE)
        & recharge["dealer_id"].isin(FLAG_DEALERS)
        & recharge["term_days"].eq(365)
    ]
    day = recharge[recharge["posted_at"].dt.normalize().eq(FLAG_DATE)]
    controls = imports[
        imports["posted_at"].dt.normalize().eq(FLAG_DATE)
        & imports["dealer_id"].isin(FLAG_DEALERS)
    ]

    duplicate_business_keys = int(
        flagged.duplicated(
            ["subscriber_id", "effective_event_date", "plan_id", "amount_usd"],
            keep=False,
        ).sum()
    )
    log_exceptions = controls[
        controls["rows_received"].ne(controls["rows_accepted"])
        | controls["duplicate_source_event_ids"].ne(0)
        | controls["reconciliation_difference_usd"].abs().gt(1e-9)
        | controls["status"].ne("RECONCILED")
    ]

    dealer_checks = []
    for dealer, rows in flagged.groupby("dealer_id"):
        control = controls[controls["dealer_id"].eq(dealer)].iloc[0]
        dealer_checks.append(
            {
                "dealer_id": dealer,
                "rows": int(len(rows)),
                "unique_source_events": int(rows["source_event_id"].nunique()),
                "amount_usd": round(float(rows["amount_usd"].sum()), 2),
                "effective_min": str(rows["effective_event_date"].min().date()),
                "effective_max": str(rows["effective_event_date"].max().date()),
                "log_rows_accepted": int(control["rows_accepted"]),
                "log_ledger_total_usd": round(float(control["ledger_total_usd"]), 2),
            }
        )

    monthly_postings = (
        recharge[
            recharge["dealer_id"].isin(FLAG_DEALERS)
            & recharge["term_days"].eq(365)
            & recharge["posted_at"].dt.month.between(3, 6)
        ]
        .assign(month=lambda x: x["posted_at"].dt.strftime("%Y-%m"))
        .groupby(["month", "dealer_id"])
        .size()
        .rename("rows")
        .reset_index()
        .to_dict("records")
    )

    return {
        "source_rows": len(recharge),
        "global_duplicate_recharge_ids": int(recharge["recharge_id"].duplicated().sum()),
        "global_duplicate_source_event_ids": int(recharge["source_event_id"].duplicated().sum()),
        "flagged_rows": int(len(flagged)),
        "flagged_amount_usd": round(float(flagged["amount_usd"].sum()), 2),
        "flagged_share_of_may31_amount_pct": round(
            100 * float(flagged["amount_usd"].sum()) / float(day["amount_usd"].sum()), 1
        ),
        "duplicate_business_key_rows": duplicate_business_keys,
        "control_exceptions": int(len(log_exceptions)),
        "dealer_checks": dealer_checks,
        "monthly_posting_pattern": monthly_postings,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.data_dir), indent=2, default=str))
