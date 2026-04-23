from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


TESTS_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(TESTS_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_SCRIPTS_DIR))

from workflow_test_support import (  # noqa: E402
    PLAN_EXAMPLE_PATH,
    example_plan,
    load_metrics_lib,
    load_planning_lib,
    load_workflow_lib,
    load_workflow_router_lib,
    rebase_execution_state_paths,
    run_workflow_state_command,
    save_example_uat_artifact,
    write_supporting_planning_artifacts,
)


def _build_execution_state(workflow_lib, tmpdir: str) -> dict:
    return rebase_execution_state_paths(
        workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md"),
        tmpdir,
    )


def test_approve_planning_uses_planning_metrics_root_when_execution_path_differs():
    planning_lib = load_planning_lib()
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_root = Path(tmpdir) / "planning"
        execution_root = Path(tmpdir) / "execution"
        planning_state_path = planning_root / "planning_state.json"
        execution_state_path = execution_root / "state.json"

        workflow_router.start_planning(
            "Plan a split-path approval flow",
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

        state = planning_lib.load_planning_state(planning_state_path)
        assert state is not None
        state = planning_lib.set_planning_status(state, "approval_ready")
        planning_lib.save_planning_state(state, planning_state_path)
        Path(state["approved_plan_path"]).write_text(PLAN_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        write_supporting_planning_artifacts(
            state,
            preserved_interfaces=[
                "Example module public behavior contract",
                "Second example module public behavior contract",
            ],
            active_initiative="Deliver the example feature as two approval-ready, commit-worthy slices.",
        )

        execution_state = planning_lib.approve_planning(
            state,
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )
        planning_metrics_dir = planning_root / "metrics"
        planning_scorecard = json.loads((planning_metrics_dir / "scorecard.json").read_text(encoding="utf-8"))
        planning_events = [
            json.loads(line)
            for line in (planning_metrics_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]

    assert execution_state["metrics_dir"] == str(planning_root / "metrics")
    assert [event["event"] for event in planning_events] == [
        "planning_started",
        "planning_approved",
        "execution_activated",
    ]
    assert planning_scorecard["counts"]["planning_started"] == 1
    assert planning_scorecard["counts"]["planning_approved"] == 1
    assert planning_scorecard["counts"]["execution_activated"] == 1
    assert (execution_root / "metrics" / "scorecard.json").exists() is False


def test_cancel_workflow_emits_metrics_event():
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        workflow_router.start_planning(
            "Plan a cancel flow",
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

        response = workflow_router.cancel_workflow(
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )
        metrics_dir = Path(tmpdir) / "metrics"
        scorecard = json.loads((metrics_dir / "scorecard.json").read_text(encoding="utf-8"))
        events = [
            json.loads(line)
            for line in (metrics_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]

    assert response.status == "ok"
    assert events[-1]["event"] == "workflow_canceled"
    assert scorecard["counts"]["workflow_canceled"] == 1


def test_metrics_scorecard_aggregates_representative_event_sequence():
    metrics_lib = load_metrics_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        metrics_dir = Path(tmpdir) / "metrics"
        metrics_lib.ensure_metrics_store(metrics_dir)
        metrics_lib.append_metrics_event(metrics_dir, "planning_started", timestamp="2026-01-01T00:00:00Z")
        metrics_lib.append_metrics_event(metrics_dir, "planning_revised", timestamp="2026-01-01T00:00:10Z")
        metrics_lib.append_metrics_event(metrics_dir, "planning_approved", timestamp="2026-01-01T00:00:20Z")
        metrics_lib.append_metrics_event(metrics_dir, "execution_activated", timestamp="2026-01-01T00:00:21Z")
        metrics_lib.append_metrics_event(metrics_dir, "review_failed", timestamp="2026-01-01T00:00:30Z")
        metrics_lib.append_metrics_event(metrics_dir, "review_passed", timestamp="2026-01-01T00:00:40Z")
        metrics_lib.append_metrics_event(metrics_dir, "step_committed", timestamp="2026-01-01T00:00:50Z")
        metrics_lib.append_metrics_event(metrics_dir, "override_used", timestamp="2026-01-01T00:00:55Z")
        metrics_lib.append_metrics_event(metrics_dir, "uat_failed_gap", timestamp="2026-01-01T00:01:00Z")
        metrics_lib.append_metrics_event(metrics_dir, "uat_passed", timestamp="2026-01-01T00:01:20Z")
        metrics_lib.append_metrics_event(metrics_dir, "workflow_shipped", timestamp="2026-01-01T00:01:40Z")

        scorecard = json.loads((metrics_dir / "scorecard.json").read_text(encoding="utf-8"))
        events = (metrics_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()

    assert len(events) == 11
    assert scorecard["plan_approval_rate"] == 1.0
    assert scorecard["revision_count_per_plan"] == 1.0
    assert scorecard["review_findings_per_step"] == 1.0
    assert scorecard["verification_failure_rate"] == 0.5
    assert scorecard["uat_failure_rate"] == 0.5
    assert scorecard["time_to_green"]["latest_seconds"] == 80.0
    assert scorecard["time_to_ship"]["latest_seconds"] == 100.0
    assert scorecard["human_override_frequency"] == round(1 / 11, 4)
    assert scorecard["deterministic_sensor_failure_count"] == 0
    assert scorecard["repeated_review_failure_count"] == 0
    assert scorecard["repeated_uat_gap_count"] == 0
    assert scorecard["escalation_counts_by_category"] == {}
    assert scorecard["escalation_frequency"]["total"] == 0


def test_metrics_scorecard_summarizes_escalations_and_repeated_loops():
    metrics_lib = load_metrics_lib()

    scorecard = metrics_lib.build_scorecard(
        [
            {"event": "planning_started", "timestamp": "2026-01-01T00:00:00Z"},
            {"event": "planning_approved", "timestamp": "2026-01-01T00:00:05Z"},
            {"event": "execution_activated", "timestamp": "2026-01-01T00:00:06Z"},
            {
                "event": "deterministic_sensor_failed",
                "timestamp": "2026-01-01T00:00:10Z",
                "category": "verification_missing",
            },
            {
                "event": "execution_escalation_entered",
                "timestamp": "2026-01-01T00:00:11Z",
                "category": "verification_missing",
            },
            {
                "event": "execution_escalation_cleared",
                "timestamp": "2026-01-01T00:00:20Z",
                "category": "verification_missing",
            },
            {"event": "review_failed", "timestamp": "2026-01-01T00:00:30Z"},
            {"event": "review_failed_repeated", "timestamp": "2026-01-01T00:00:40Z"},
            {"event": "uat_failed_gap", "timestamp": "2026-01-01T00:00:50Z"},
            {"event": "uat_gap_repeated", "timestamp": "2026-01-01T00:01:00Z"},
            {"event": "workflow_shipped", "timestamp": "2026-01-01T00:01:20Z"},
        ]
    )

    assert scorecard["deterministic_sensor_failure_count"] == 1
    assert scorecard["repeated_review_failure_count"] == 1
    assert scorecard["repeated_uat_gap_count"] == 1
    assert scorecard["escalation_counts_by_category"] == {"verification_missing": 1}
    assert scorecard["escalation_frequency"]["total"] == 1
    assert scorecard["escalation_frequency"]["latest_per_workflow"] == 1


def test_metrics_scorecard_drops_canceled_session_from_timing_queue():
    metrics_lib = load_metrics_lib()

    scorecard = metrics_lib.build_scorecard(
        [
            {"event": "planning_started", "timestamp": "2026-01-01T00:00:00Z"},
            {"event": "workflow_canceled", "timestamp": "2026-01-01T00:00:10Z"},
            {"event": "planning_started", "timestamp": "2026-01-01T00:00:20Z"},
            {"event": "planning_approved", "timestamp": "2026-01-01T00:00:25Z"},
            {"event": "execution_activated", "timestamp": "2026-01-01T00:00:26Z"},
            {"event": "uat_passed", "timestamp": "2026-01-01T00:00:40Z"},
            {"event": "workflow_shipped", "timestamp": "2026-01-01T00:00:50Z"},
        ]
    )

    assert scorecard["time_to_green"]["latest_seconds"] == 20.0
    assert scorecard["time_to_ship"]["latest_seconds"] == 30.0
    assert scorecard["counts"]["workflow_canceled"] == 1


def test_metrics_scorecard_drops_abandoned_open_session_when_new_planning_starts():
    metrics_lib = load_metrics_lib()

    scorecard = metrics_lib.build_scorecard(
        [
            {"event": "planning_started", "timestamp": "2026-01-01T00:00:00Z"},
            {"event": "planning_started", "timestamp": "2026-01-01T00:00:20Z"},
            {"event": "planning_approved", "timestamp": "2026-01-01T00:00:25Z"},
            {"event": "execution_activated", "timestamp": "2026-01-01T00:00:26Z"},
            {"event": "uat_passed", "timestamp": "2026-01-01T00:00:40Z"},
            {"event": "workflow_shipped", "timestamp": "2026-01-01T00:00:50Z"},
        ]
    )

    assert scorecard["time_to_green"]["latest_seconds"] == 20.0
    assert scorecard["time_to_ship"]["latest_seconds"] == 30.0


def test_workflow_state_emits_review_uat_ship_and_override_metrics():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["status"] = "implementing"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(workflow_lib, state)

        commands = [
            (
                "set-step-status",
                "step-1",
                "review_pending",
            ),
            (
                "set-step-status",
                "step-1",
                "fix_pending",
                "--review-summary",
                "Missing regression assertion.",
            ),
            (
                "set-step-status",
                "step-1",
                "review_pending",
            ),
            (
                "set-step-status",
                "step-1",
                "commit_pending",
                "--review-summary",
                "review passed",
            ),
            (
                "set-step-status",
                "step-1",
                "committed",
            ),
            (
                "set-workflow-status",
                "uat_pending",
                "--override-reason",
                "manual workflow-status reconciliation",
            ),
            (
                "set-uat-status",
                "failed-gap",
                "--summary",
                "One fixable verification gap remains.",
            ),
            (
                "set-step-status",
                "step-1",
                "review_pending",
            ),
            (
                "set-step-status",
                "step-1",
                "commit_pending",
                "--review-summary",
                "gap fix review passed",
            ),
            (
                "set-step-status",
                "step-1",
                "committed",
            ),
            (
                "set-uat-status",
                "passed",
                "--summary",
                "Final UAT passed.",
            ),
            (
                "set-step-status",
                "step-1",
                "shipped",
            ),
            (
                "set-workflow-status",
                "complete",
            ),
        ]

        for command in commands:
            result = run_workflow_state_command(state_path, *command)
            assert result.returncode == 0, result.stderr

        events_path = Path(state["metrics_dir"]) / "events.jsonl"
        scorecard_path = Path(state["metrics_dir"]) / "scorecard.json"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
        scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))

    assert [event["event"] for event in events] == [
        "review_failed",
        "review_passed",
        "step_committed",
        "override_used",
        "uat_failed_gap",
        "review_passed",
        "step_committed",
        "uat_passed",
        "workflow_shipped",
    ]
    assert scorecard["counts"]["review_failed"] == 1
    assert scorecard["counts"]["review_passed"] == 2
    assert scorecard["counts"]["step_committed"] == 2
    assert scorecard["counts"]["override_used"] == 1
    assert scorecard["counts"]["uat_failed_gap"] == 1
    assert scorecard["counts"]["uat_passed"] == 1
    assert scorecard["counts"]["workflow_shipped"] == 1


def test_workflow_state_emits_escalation_and_repeated_loop_metrics():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["verify_cmds"] = []
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(workflow_lib, state)

        failed_review_gate = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        escalated_state = workflow_lib.load_state(state_path)
        escalated_state["steps"][0]["verify_cmds"] = ["uv run pytest tests/ai/test_embedding_service.py"]
        workflow_lib.save_state(escalated_state, state_path)

        follow_up_commands = [
            ("resolve-escalation",),
            ("set-step-status", "step-1", "review_pending"),
            (
                "set-step-status",
                "step-1",
                "fix_pending",
                "--review-summary",
                "Missing regression assertion.",
            ),
            ("set-step-status", "step-1", "review_pending"),
            (
                "set-step-status",
                "step-1",
                "fix_pending",
                "--review-summary",
                "Missing regression assertion again.",
            ),
            ("set-step-status", "step-1", "review_pending"),
            (
                "set-step-status",
                "step-1",
                "commit_pending",
                "--review-summary",
                "review passed",
            ),
            ("set-step-status", "step-1", "committed"),
            (
                "set-workflow-status",
                "uat_pending",
                "--override-reason",
                "manual workflow-status reconciliation",
            ),
            (
                "set-uat-status",
                "failed-gap",
                "--summary",
                "One fixable verification gap remains.",
            ),
            ("set-step-status", "step-1", "review_pending"),
            (
                "set-step-status",
                "step-1",
                "commit_pending",
                "--review-summary",
                "gap fix review passed",
            ),
            ("set-step-status", "step-1", "committed"),
            (
                "set-uat-status",
                "failed-gap",
                "--summary",
                "Another small gap remains.",
            ),
        ]

        for command in follow_up_commands:
            result = run_workflow_state_command(state_path, *command)
            assert result.returncode == 0, result.stderr

        events_path = Path(state["metrics_dir"]) / "events.jsonl"
        scorecard_path = Path(state["metrics_dir"]) / "scorecard.json"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
        scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))

    assert failed_review_gate.returncode != 0
    assert [event["event"] for event in events] == [
        "deterministic_sensor_failed",
        "execution_escalation_entered",
        "execution_escalation_cleared",
        "review_failed",
        "review_failed",
        "review_failed_repeated",
        "review_passed",
        "step_committed",
        "override_used",
        "uat_failed_gap",
        "review_passed",
        "step_committed",
        "uat_failed_gap",
        "uat_gap_repeated",
    ]
    assert events[0]["category"] == "verification_missing"
    assert events[1]["category"] == "verification_missing"
    assert events[2]["category"] == "verification_missing"
    assert scorecard["counts"]["deterministic_sensor_failed"] == 1
    assert scorecard["counts"]["execution_escalation_entered"] == 1
    assert scorecard["counts"]["execution_escalation_cleared"] == 1
    assert scorecard["counts"]["review_failed_repeated"] == 1
    assert scorecard["counts"]["uat_gap_repeated"] == 1
    assert scorecard["deterministic_sensor_failure_count"] == 1
    assert scorecard["repeated_review_failure_count"] == 1
    assert scorecard["repeated_uat_gap_count"] == 1
    assert scorecard["escalation_counts_by_category"] == {"verification_missing": 1}
