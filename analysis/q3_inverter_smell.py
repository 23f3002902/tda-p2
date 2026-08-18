"""Summarize the small inverter-event extract without over-interpreting labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def analyze(data_dir: Path) -> dict:
    events = pd.read_csv(data_dir / "inverter_events.csv")
    warnings = events[events["severity"].eq("warning")]
    return {
        "rows": int(len(events)),
        "severity_counts": {k: int(v) for k, v in events["severity"].value_counts().items()},
        "total_duration_min": int(events["duration_min"].sum()),
        "max_duration_min": int(events["duration_min"].max()),
        "total_reported_impact_mw": float(events["impact_mw"].sum()),
        "all_cleared": bool(events["cleared"].str.lower().eq("yes").all()),
        "warning_rows": warnings.to_dict("records"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.data_dir), indent=2))
