"""Recompute the reported DSM comparison and a same-day base-schedule check."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


CONTROL_DAY = pd.Timestamp("2026-05-28")
PILOT_DAY = pd.Timestamp("2026-05-29")


def analyze(data_dir: Path) -> dict:
    blocks = pd.read_csv(data_dir / "dispatch_blocks.csv", parse_dates=["date"])
    blocks["schedule_mwh"] = blocks["submitted_schedule_mw"] * 0.25
    blocks["actual_mwh"] = blocks["actual_mw"] * 0.25
    blocks["absolute_gap_mwh"] = (
        blocks["submitted_schedule_mw"].sub(blocks["actual_mw"]).abs() * 0.25
    )
    blocks["calculated_penalty_rs"] = (
        blocks["absolute_gap_mwh"] * 1000 * blocks["dsm_rate_rs_kwh"]
    )

    daily = blocks.groupby("date").agg(
        blocks=("block_no", "size"),
        schedule_mwh=("schedule_mwh", "sum"),
        actual_mwh=("actual_mwh", "sum"),
        absolute_gap_mwh=("absolute_gap_mwh", "sum"),
        penalty_rs=("dsm_penalty_rs", "sum"),
        calculated_penalty_rs=("calculated_penalty_rs", "sum"),
        max_local_gust_ms=("local_gust_3s_ms", "max"),
        stow_blocks=("tracker_stow_state", lambda x: int(x.ne("NORMAL").sum())),
        availability_mean=("availability_pct", "mean"),
        cloud_mean=("cloud_factor", "mean"),
    )
    control = daily.loc[CONTROL_DAY]
    pilot = daily.loc[PILOT_DAY]

    pilot_blocks = blocks[blocks["date"].eq(PILOT_DAY)].copy()
    pilot_blocks["base_counterfactual_penalty_rs"] = (
        pilot_blocks["base_schedule_mw"]
        .sub(pilot_blocks["actual_mw"])
        .abs()
        .mul(0.25 * 1000)
        .mul(pilot_blocks["dsm_rate_rs_kwh"])
    )
    revised = pilot_blocks["base_schedule_mw"].ne(pilot_blocks["submitted_schedule_mw"])
    counterfactual = float(pilot_blocks["base_counterfactual_penalty_rs"].sum())
    observed_calculated = float(pilot_blocks["calculated_penalty_rs"].sum())

    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(data_dir / "DSM_Commercial_Extract.pdf").pages)

    high_wind_days = daily[daily["stow_blocks"].gt(0)][
        ["penalty_rs", "max_local_gust_ms", "stow_blocks"]
    ]
    return {
        "control_day": {k: round(float(v), 2) for k, v in control.items()},
        "pilot_day": {k: round(float(v), 2) for k, v in pilot.items()},
        "reported_pairwise_penalty_reduction_pct": round(
            100 * (1 - pilot["penalty_rs"] / control["penalty_rs"]), 3
        ),
        "reported_pairwise_gap_reduction_pct": round(
            100 * (1 - pilot["absolute_gap_mwh"] / control["absolute_gap_mwh"]), 3
        ),
        "pilot_revised_blocks": int(revised.sum()),
        "pilot_schedule_reduction_vs_base_mwh": round(
            float(
                pilot_blocks["base_schedule_mw"]
                .sub(pilot_blocks["submitted_schedule_mw"])
                .mul(0.25)
                .sum()
            ),
            2,
        ),
        "same_day_base_counterfactual": {
            "penalty_rs": round(counterfactual, 2),
            "observed_calculated_penalty_rs": round(observed_calculated, 2),
            "difference_rs": round(counterfactual - observed_calculated, 2),
            "reduction_pct": round(100 * (1 - observed_calculated / counterfactual), 2),
            "assumption": "actual output and each block DSM rate remain fixed",
        },
        "high_wind_days": {
            str(day.date()): {k: round(float(v), 2) for k, v in row.items()}
            for day, row in high_wind_days.iterrows()
        },
        "commercial_extract_checks": {
            "uses_accepted_schedule": "accepted schedule" in pdf_text.lower(),
            "not_full_regulation": "not the full regulation" in pdf_text.lower(),
            "energy_tariff_rs_kwh": 2.72 if "2.72/kWh" in pdf_text.replace(" ", "") else None,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.data_dir), indent=2))
