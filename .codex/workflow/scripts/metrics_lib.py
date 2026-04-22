from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENTS_FILE_NAME = "events.jsonl"
SCORECARD_FILE_NAME = "scorecard.json"


def append_metrics_event(
    metrics_dir: Path | str,
    event: str,
    *,
    details: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    metrics_root = Path(metrics_dir)
    events_path = metrics_root / EVENTS_FILE_NAME
    scorecard_path = metrics_root / SCORECARD_FILE_NAME
    metrics_root.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "timestamp": timestamp or utc_now_iso(),
        "event": event,
    }
    if details:
        payload.update(details)

    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")

    scorecard = build_scorecard(load_metrics_events(metrics_root))
    scorecard_path.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")
    return payload


def ensure_metrics_store(metrics_dir: Path | str) -> None:
    metrics_root = Path(metrics_dir)
    metrics_root.mkdir(parents=True, exist_ok=True)
    events_path = metrics_root / EVENTS_FILE_NAME
    scorecard_path = metrics_root / SCORECARD_FILE_NAME
    if not events_path.exists():
        events_path.write_text("", encoding="utf-8")
    if not scorecard_path.exists():
        scorecard_path.write_text(json.dumps(build_scorecard([]), indent=2) + "\n", encoding="utf-8")


def load_metrics_events(metrics_dir: Path | str) -> list[dict[str, Any]]:
    events_path = Path(metrics_dir) / EVENTS_FILE_NAME
    if not events_path.exists():
        return []

    events: list[dict[str, Any]] = []
    for raw_line in events_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("metrics event log must contain JSON objects")
        events.append(event)
    return events


def build_scorecard(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    queue: list[dict[str, Any]] = []
    time_to_green_samples: list[float] = []
    time_to_ship_samples: list[float] = []
    latest_timestamp: str | None = None

    for entry in events:
        event = str(entry.get("event") or "").strip()
        timestamp_value = str(entry.get("timestamp") or "").strip()
        if not event or not timestamp_value:
            continue

        counts[event] += 1
        latest_timestamp = timestamp_value
        timestamp = _parse_iso8601(timestamp_value)

        if event == "planning_started":
            queue.append({"started_at": timestamp, "green_recorded": False})
            continue

        if event == "uat_failed_replan":
            if queue:
                queue.pop(0)
            continue

        if event == "uat_passed":
            if queue and not queue[0]["green_recorded"]:
                session = queue[0]
                session["green_recorded"] = True
                session["green_at"] = timestamp
                time_to_green_samples.append(
                    (timestamp - session["started_at"]).total_seconds()
                )
            continue

        if event == "workflow_shipped":
            if queue:
                session = queue.pop(0)
                time_to_ship_samples.append(
                    (timestamp - session["started_at"]).total_seconds()
                )
            continue

    plan_starts = counts["planning_started"]
    plan_approvals = counts["planning_approved"]
    review_failures = counts["review_failed"]
    review_passes = counts["review_passed"]
    committed_steps = counts["step_committed"]
    uat_failures = counts["uat_failed_gap"] + counts["uat_failed_replan"]
    uat_passes = counts["uat_passed"]
    total_gate_reviews = review_failures + review_passes

    return {
        "version": 1,
        "updated_at": latest_timestamp or utc_now_iso(),
        "event_count": len(events),
        "counts": dict(sorted(counts.items())),
        "plan_approval_rate": _safe_ratio(plan_approvals, plan_starts),
        "revision_count_per_plan": _safe_ratio(counts["planning_revised"], plan_starts),
        "review_findings_per_step": _safe_ratio(review_failures, committed_steps),
        "verification_failure_rate": _safe_ratio(review_failures, total_gate_reviews),
        "uat_failure_rate": _safe_ratio(uat_failures, uat_failures + uat_passes),
        "time_to_green": _duration_summary(time_to_green_samples),
        "time_to_ship": _duration_summary(time_to_ship_samples),
        "human_override_frequency": _safe_ratio(counts["override_used"], len(events)),
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _duration_summary(samples: list[float]) -> dict[str, Any]:
    if not samples:
        return {
            "sample_count": 0,
            "average_seconds": None,
            "latest_seconds": None,
            "minimum_seconds": None,
            "maximum_seconds": None,
        }

    rounded = [round(sample, 2) for sample in samples]
    return {
        "sample_count": len(rounded),
        "average_seconds": round(sum(samples) / len(samples), 2),
        "latest_seconds": rounded[-1],
        "minimum_seconds": min(rounded),
        "maximum_seconds": max(rounded),
    }


def _parse_iso8601(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)
