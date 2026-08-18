"""Compare South NovaIVR outcomes with a same-length pre-pilot window."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


PILOT_START = pd.Timestamp("2026-05-10")
WINDOW_DAYS = 52


def pct_change(after: int, before: int) -> float:
    return round(100 * (after / before - 1), 1)


def analyze(data_dir: Path) -> dict:
    ivr = pd.read_json(data_dir / "ivr_interactions.jsonl", lines=True)
    tickets = pd.read_csv(data_dir / "tickets.csv")
    events = pd.read_csv(data_dir / "service_events.csv")
    ivr["started_at"] = pd.to_datetime(ivr["started_at"])
    tickets["created_at"] = pd.to_datetime(tickets["created_at"])
    events["start_time"] = pd.to_datetime(events["start_time"])

    start = PILOT_START - pd.Timedelta(days=WINDOW_DAYS)
    end = PILOT_START + pd.Timedelta(days=WINDOW_DAYS)

    def period(values: pd.Series) -> pd.Series:
        return pd.Series(
            pd.NA,
            index=values.index,
            dtype="string",
        ).mask(values.between(start, PILOT_START, inclusive="left"), "pre").mask(
            values.between(PILOT_START, end, inclusive="left"), "post"
        )

    ivr["period"] = period(ivr["started_at"])
    tickets["period"] = period(tickets["created_at"])
    events["period"] = period(events["start_time"])

    ticket_counts = (
        tickets[tickets["period"].notna()]
        .groupby(["region", "period"])
        .size()
        .unstack(fill_value=0)
    )
    region_changes = {
        region: {
            "pre": int(row["pre"]),
            "post": int(row["post"]),
            "pct_change": pct_change(int(row["post"]), int(row["pre"])),
        }
        for region, row in ticket_counts.iterrows()
    }

    south = ivr[ivr["region"].eq("S") & ivr["period"].notna()]
    pre = south[south["period"].eq("pre")]
    post = south[south["period"].eq("post")]
    outcome_counts = post["outcome"].value_counts().to_dict()
    authentication_losses = post[
        post["terminal_stage"].eq("authenticate")
        & post["outcome"].isin(["ERROR", "ABANDONED"])
    ]

    ordered = post.sort_values(["subscriber_id", "started_at"]).copy()
    ordered["next_at"] = ordered.groupby("subscriber_id")["started_at"].shift(-1)
    ordered["repeat_7d"] = ordered["next_at"].sub(ordered["started_at"]).le(pd.Timedelta(days=7))
    repeats = {
        outcome: round(100 * float(group["repeat_7d"].mean()), 1)
        for outcome, group in ordered.groupby("outcome")
    }

    south_events = events[events["region"].eq("S") & events["period"].notna()]
    event_summary = south_events.groupby("period").agg(
        events=("event_id", "size"),
        affected_accounts=("affected_accounts_est", "sum"),
        high_severity=("severity", lambda x: int(x.eq("HIGH").sum())),
    )

    return {
        "windows": {"pre_start": str(start.date()), "pilot_start": str(PILOT_START.date()), "post_end": str(end.date())},
        "ticket_counts_by_region": region_changes,
        "south_ivr": {
            "pre_sessions": int(len(pre)),
            "pre_case_linked": int(pre["case_id"].notna().sum()),
            "post_sessions": int(len(post)),
            "post_case_linked": int(post["case_id"].notna().sum()),
            "post_outcomes": {k: int(v) for k, v in outcome_counts.items()},
            "post_outcome_pct": {k: round(100 * int(v) / len(post), 1) for k, v in outcome_counts.items()},
            "auth_error_or_abandon": int(len(authentication_losses)),
            "auth_error_or_abandon_pct": round(100 * len(authentication_losses) / len(post), 1),
            "repeat_within_7d_pct_by_outcome": repeats,
        },
        "south_service_events": {
            p: {k: int(v) for k, v in row.items()}
            for p, row in event_summary.to_dict("index").items()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.data_dir), indent=2))
