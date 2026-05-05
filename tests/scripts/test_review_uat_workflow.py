from __future__ import annotations

import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path


TESTS_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(TESTS_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_SCRIPTS_DIR))

from workflow_test_support import (  # noqa: E402
    STATE_EXAMPLE_PATH,
    example_plan,
    load_workflow_lib,
    load_workflow_router_lib,
    rebase_execution_state_paths,
    run_workflow_state_command,
    save_example_uat_artifact,
)


def _build_execution_state(workflow_lib, tmpdir: str) -> dict:
    return rebase_execution_state_paths(
        workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md"),
        tmpdir,
    )


def _review_args(
    *,
    summary: str,
    scope_confirmed: bool = True,
    verification_status: str = "passed",
    verification_note: str | None = None,
    agents_checked: list[str] | None = None,
    agents_updated: bool = False,
    finding_count: int,
) -> tuple[str, ...]:
    args = [
        "--review-summary",
        summary,
        "--scope-confirmed",
        "true" if scope_confirmed else "false",
        "--verification-status",
        verification_status,
    ]
    if verification_note is not None:
        args.extend(["--verification-note", verification_note])
    for path in agents_checked or ["AGENTS.md"]:
        args.extend(["--agents-checked", path])
    args.extend(
        [
            "--agents-updated",
            "true" if agents_updated else "false",
            "--finding-count",
            str(finding_count),
        ]
    )
    return tuple(args)


def _prepare_review_pending_state(
    workflow_lib,
    tmpdir: str,
    *,
    agents_paths: list[str] | None = None,
    agents_update_required: bool | None = None,
) -> Path:
    state_path = Path(tmpdir) / "state.json"
    state = _build_execution_state(workflow_lib, tmpdir)
    if agents_paths is not None:
        state["steps"][0]["agents_paths"] = agents_paths
    if agents_update_required is not None:
        state["steps"][0]["agents_update_required"] = agents_update_required
    workflow_lib.save_state(state, state_path)
    review_result = run_workflow_state_command(
        state_path,
        "set-step-status",
        "step-1",
        "review_pending",
    )
    assert review_result.returncode == 0, review_result.stderr
    return state_path


def test_review_pending_step_blocks_for_review_gate():
    workflow_lib = load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["steps"][0]["status"] = "review_pending"

    _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert decision.action == "block"
    assert "code_review.md" in decision.prompt
    assert "python3 .codex/workflow/scripts/workflow_state.py set-step-status step-1 commit_pending" in decision.prompt
    assert "--scope-confirmed true" in decision.prompt
    assert "--agents-checked AGENTS.md" in decision.prompt
    assert "--finding-count 0" in decision.prompt


def test_review_pending_prompt_surfaces_required_checks_for_guidance_updates():
    workflow_lib = load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["steps"][0]["status"] = "review_pending"
    state["steps"][0]["agents_update_required"] = True

    _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert decision.action == "block"
    assert "Required checks before pass" in decision.prompt
    assert "Relevant verification commands ran" in decision.prompt
    assert "Review scope stayed inside the current execution step" in decision.prompt
    assert "Every required AGENTS.md path was checked" in decision.prompt
    assert "a passing review must use --agents-updated true" in decision.prompt


def test_workflow_state_review_pending_requires_pre_review_sensors():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["verify_cmds"] = []
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "deterministic pre-review sensors" in result.stderr
    assert persisted_state["workflow_status"] == "execution_escalated"
    assert persisted_state["steps"][0]["status"] == "implementing"
    assert persisted_state["escalation"]["code"] == "verification_missing"


def test_workflow_state_review_pending_accepts_pytest_node_id_for_file_target():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["verify_cmds"] = [
            "uv run pytest tests/ai/test_embedding_service.py::test_updates_embedding_behavior"
        ]
        state["steps"][0]["verification_targets"] = ["tests/ai/test_embedding_service.py"]
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "active"
    assert persisted_state["escalation"] is None
    assert persisted_state["steps"][0]["status"] == "review_pending"


def test_workflow_state_review_pending_accepts_dot_slash_prefixed_verification_path():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["verify_cmds"] = ["uv run pytest ./tests/ai/test_embedding_service.py"]
        state["steps"][0]["verification_targets"] = ["tests/ai/test_embedding_service.py"]
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "active"
    assert persisted_state["escalation"] is None
    assert persisted_state["steps"][0]["status"] == "review_pending"


def test_workflow_state_review_pending_rejects_malformed_verify_command_deterministically():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["verify_cmds"] = ['uv run pytest "tests/ai/test_embedding_service.py']
        state["steps"][0]["verification_targets"] = ["tests/ai/test_embedding_service.py"]
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "deterministic pre-review sensors" in result.stderr
    assert "malformed shell quoting" in result.stderr
    assert persisted_state["workflow_status"] == "execution_escalated"
    assert persisted_state["steps"][0]["status"] == "implementing"
    assert persisted_state["escalation"]["code"] == "verification_missing"
    assert "invalid verify_cmd shell quoting" in persisted_state["escalation"]["details"][0]["details"]["error"]


def test_final_committed_step_enters_uat_pending_mode():
    workflow_lib = load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["current_step_id"] = "step-2"
    state["steps"][0]["status"] = "committed"
    state["steps"][1]["status"] = "committed"
    state["uat_artifact_path"] = str(STATE_EXAMPLE_PATH.parent / "uat.json")

    new_state, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is True
    assert new_state["workflow_status"] == "uat_pending"
    assert decision.action == "block"
    assert "set-uat-status passed" in decision.prompt


def test_uat_pending_blocks_with_uat_prompt():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        save_example_uat_artifact(workflow_lib, state)

        _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert "user-acceptance gate" in decision.prompt
    assert "set-uat-status failed-gap" in decision.prompt


def test_gap_closure_pending_returns_to_uat_after_fix_commit():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "gap_closure_pending"
        state["steps"][0]["status"] = "committed"
        save_example_uat_artifact(workflow_lib, state)

        new_state, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is True
    assert new_state["workflow_status"] == "uat_pending"
    assert "set-uat-status passed" in decision.prompt


def test_replan_required_blocks_with_follow_up_planning_prompt():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "replan_required"
        state["steps"][0]["status"] = "committed"
        save_example_uat_artifact(workflow_lib, state)
        workflow_lib.update_uat_artifact_result(
            Path(state["uat_artifact_path"]),
            "failed_replan",
            "The approved architecture no longer matches the required scope.",
        )

        _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert "cannot ship" in decision.prompt
    assert "follow-up planning session" in decision.prompt


def test_workflow_state_commit_pending_rejected_without_review_evidence():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "set-step-status commit_pending rejected" in result.stderr
    assert "--review-summary" in result.stderr
    assert persisted_state["steps"][0]["status"] == "review_pending"
    assert persisted_state["steps"][0]["review_record"] is None


def test_workflow_state_commit_pending_rejected_when_finding_count_is_positive():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(summary="review passed", finding_count=1),
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "--finding-count 0" in result.stderr
    assert persisted_state["steps"][0]["status"] == "review_pending"


def test_workflow_state_commit_pending_rejected_when_scope_is_not_confirmed():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(summary="review passed", scope_confirmed=False, finding_count=0),
        )

    assert result.returncode != 0
    assert "--scope-confirmed true" in result.stderr


def test_workflow_state_commit_pending_rejected_when_verification_is_blocked():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(
                summary="review passed",
                verification_status="blocked",
                verification_note="pytest is failing in CI",
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "--verification-status passed" in result.stderr


def test_workflow_state_commit_pending_rejected_when_agents_checked_omit_required_path():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(
            workflow_lib,
            tmpdir,
            agents_paths=["AGENTS.md", "docs/AGENTS.md"],
        )

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(
                summary="review passed",
                agents_checked=["AGENTS.md"],
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "docs/AGENTS.md" in result.stderr


def test_workflow_state_commit_pending_rejected_when_required_agents_update_is_not_recorded():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(
            workflow_lib,
            tmpdir,
            agents_update_required=True,
        )

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(summary="review passed", agents_updated=False, finding_count=0),
        )

    assert result.returncode != 0
    assert "--agents-updated true" in result.stderr
    assert "agents_update_required" in result.stderr


def test_workflow_state_commit_pending_accepts_recorded_required_agents_update():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(
            workflow_lib,
            tmpdir,
            agents_update_required=True,
        )

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(summary="review passed", agents_updated=True, finding_count=0),
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode == 0, result.stderr
    assert persisted_state["steps"][0]["status"] == "commit_pending"
    assert persisted_state["steps"][0]["review_record"]["agents_updated"] is True


def test_plan_step_infers_required_agents_update_from_agents_path_changes():
    workflow_lib = load_workflow_lib()
    plan = example_plan()
    plan["steps"][0]["planned_updates"].append("AGENTS.md")

    state = workflow_lib.build_state_from_plan_spec(plan, plan_path="PLANS.md")

    assert state["steps"][0]["agents_update_required"] is True


def test_workflow_state_fix_pending_rejected_when_finding_count_is_zero():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "fix_pending",
            *_review_args(summary="Missing regression assertion.", finding_count=0),
        )

    assert result.returncode != 0
    assert "greater than 0" in result.stderr


def test_workflow_state_fix_pending_rejected_when_blocked_verification_has_no_note():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "fix_pending",
            *_review_args(
                summary="Missing regression assertion.",
                verification_status="blocked",
                finding_count=1,
            ),
        )

    assert result.returncode != 0
    assert "--verification-note" in result.stderr


def test_workflow_state_fix_pending_persists_review_record():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "fix_pending",
            *_review_args(summary="Missing regression assertion.", finding_count=2),
        )
        persisted_state = workflow_lib.load_state(state_path)
        review_record = persisted_state["steps"][0]["review_record"]

    assert result.returncode == 0, result.stderr
    assert persisted_state["steps"][0]["status"] == "fix_pending"
    assert persisted_state["steps"][0]["review_summary"] == "Missing regression assertion."
    assert review_record["outcome"] == "failed"
    assert review_record["summary"] == "Missing regression assertion."
    assert review_record["scope_confirmed"] is True
    assert review_record["verification_status"] == "passed"
    assert review_record["verification_note"] is None
    assert review_record["agents_checked"] == ["AGENTS.md"]
    assert review_record["agents_updated"] is False
    assert review_record["finding_count"] == 2
    assert review_record["checked_at"].endswith("Z")


def test_workflow_state_commit_pending_persists_review_record():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(summary="review passed", finding_count=0),
        )
        persisted_state = workflow_lib.load_state(state_path)
        review_record = persisted_state["steps"][0]["review_record"]

    assert result.returncode == 0, result.stderr
    assert persisted_state["steps"][0]["status"] == "commit_pending"
    assert review_record["outcome"] == "passed"
    assert review_record["finding_count"] == 0
    assert review_record["verification_status"] == "passed"


def test_workflow_state_review_summary_compatibility_remains_intact():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(summary="review passed", finding_count=0),
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode == 0, result.stderr
    assert persisted_state["steps"][0]["review_summary"] == "review passed"
    assert persisted_state["steps"][0]["review_record"]["summary"] == "review passed"


def test_resume_surfaces_execution_escalation_for_invalid_review_state():
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["status"] = "review_pending"
        state["steps"][0]["verify_cmds"] = []
        workflow_lib.save_state(state, state_path)

        response = workflow_router.resume_workflow(
            planning_state_path=planning_state_path,
            execution_state_path=state_path,
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert response.status == "ok"
    assert response.message == "workflow execution escalated"
    assert "verification_missing" in response.additional_context
    assert persisted_state["workflow_status"] == "execution_escalated"
    assert persisted_state["steps"][0]["status"] == "review_pending"
    assert persisted_state["escalation"]["code"] == "verification_missing"


def test_resolve_escalation_returns_workflow_to_active_execution():
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["verify_cmds"] = []
        workflow_lib.save_state(state, state_path)

        failed_review = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        escalated_state = workflow_lib.load_state(state_path)
        escalated_state["steps"][0]["verify_cmds"] = ["uv run pytest tests/ai/test_embedding_service.py"]
        workflow_lib.save_state(escalated_state, state_path)

        resolve_result = run_workflow_state_command(
            state_path,
            "resolve-escalation",
        )
        persisted_state = workflow_lib.load_state(state_path)
        response = workflow_router.resume_workflow(
            planning_state_path=planning_state_path,
            execution_state_path=state_path,
        )

    assert failed_review.returncode != 0
    assert resolve_result.returncode == 0, resolve_result.stderr
    assert persisted_state["workflow_status"] == "active"
    assert persisted_state["escalation"] is None
    assert "Start the next execution step." not in response.additional_context
    assert "Do not stop yet." in response.additional_context


def test_resolve_escalation_restores_prior_non_active_phase():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "ship_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)

        escalate_result = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "execution_escalated",
            "--override-reason",
            "manual ship-phase escalation for verification",
        )
        escalated_state = workflow_lib.load_state(state_path)

        resolve_result = run_workflow_state_command(
            state_path,
            "resolve-escalation",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert escalate_result.returncode == 0, escalate_result.stderr
    assert escalated_state["workflow_status"] == "execution_escalated"
    assert escalated_state["escalation"]["resume_status"] == "ship_pending"
    assert resolve_result.returncode == 0, resolve_result.stderr
    assert persisted_state["workflow_status"] == "ship_pending"
    assert persisted_state["escalation"] is None


def test_workflow_state_set_uat_status_passed_updates_state_and_artifact():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(workflow_lib, state)

        result = run_workflow_state_command(
            state_path,
            "set-uat-status",
            "passed",
            "--summary",
            "UAT passed cleanly.",
        )

        persisted_state = workflow_lib.load_state(state_path)
        uat_artifact = workflow_lib.load_uat_artifact(Path(state["uat_artifact_path"]))

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "ship_pending"
    assert uat_artifact["overall_status"] == "passed"
    assert uat_artifact["summary"] == "UAT passed cleanly."


def test_workflow_state_set_uat_status_failed_gap_transitions_to_gap_closure():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(workflow_lib, state)

        result = run_workflow_state_command(
            state_path,
            "set-uat-status",
            "failed-gap",
            "--summary",
            "One fixable verification gap remains.",
        )

        persisted_state = workflow_lib.load_state(state_path)
        uat_artifact = workflow_lib.load_uat_artifact(Path(state["uat_artifact_path"]))

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "gap_closure_pending"
    assert persisted_state["steps"][0]["status"] == "implementing"
    assert persisted_state["steps"][0]["review_summary"] == "One fixable verification gap remains."
    assert uat_artifact["overall_status"] == "failed_gap"


def test_workflow_state_set_uat_status_failed_replan_transitions_to_replan_required():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(workflow_lib, state)

        result = run_workflow_state_command(
            state_path,
            "set-uat-status",
            "failed-replan",
            "--summary",
            "The approved architecture no longer matches the needed scope.",
        )

        persisted_state = workflow_lib.load_state(state_path)
        uat_artifact = workflow_lib.load_uat_artifact(Path(state["uat_artifact_path"]))

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "replan_required"
    assert uat_artifact["overall_status"] == "failed_replan"


def test_workflow_state_set_workflow_status_requires_override_reason_for_manual_change():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["status"] = "implementing"
        workflow_lib.save_state(state, state_path)

        missing_reason = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "uat_pending",
        )
        state_after_failure = workflow_lib.load_state(state_path)

        override_result = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "uat_pending",
            "--override-reason",
            "manual reconciliation for regression coverage",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert missing_reason.returncode != 0
    assert "manual override" in missing_reason.stderr
    assert state_after_failure["workflow_status"] == "active"
    assert override_result.returncode == 0, override_result.stderr
    assert persisted_state["workflow_status"] == "uat_pending"


def test_workflow_state_set_workflow_status_complete_requires_ship_pending_and_shipped():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)

        wrong_status = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "complete",
        )

        state["workflow_status"] = "ship_pending"
        workflow_lib.save_state(state, state_path)
        not_shipped = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "complete",
        )
        persisted_state = workflow_lib.load_state(state_path)
        metrics_exists = (Path(state["metrics_dir"]) / "events.jsonl").exists()

    assert wrong_status.returncode != 0
    assert "ship_pending" in wrong_status.stderr
    assert not_shipped.returncode != 0
    assert "current step to be shipped" in not_shipped.stderr
    assert persisted_state["workflow_status"] == "ship_pending"
    assert metrics_exists is False


def test_next_stop_decision_escalates_shipped_state_inconsistency():
    workflow_lib = load_workflow_lib()
    state = workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md")
    state["steps"][0]["status"] = "shipped"

    next_state, decision, changed = workflow_lib.next_stop_decision(state)

    assert changed is True
    assert decision.action == "escalate"
    assert next_state["workflow_status"] == "execution_escalated"
    assert next_state["escalation"]["code"] == "manual_override"


def test_shipped_state_inconsistency_prompt_requires_manual_reconciliation():
    workflow_lib = load_workflow_lib()
    state = workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md")
    state["steps"][0]["status"] = "shipped"

    next_state, decision, changed = workflow_lib.next_stop_decision(state)

    assert changed is True
    assert next_state["workflow_status"] == "execution_escalated"
    assert "set-workflow-status ship_pending --override-reason" in (decision.prompt or "")
    assert "set-workflow-status complete" in (decision.prompt or "")
    assert "Do not run `python3 .codex/workflow/scripts/workflow_state.py resolve-escalation`" in (
        decision.prompt or ""
    )


def test_workflow_state_set_step_status_shipped_requires_ship_pending_and_committed():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        workflow_lib.save_state(state, state_path)

        wrong_status = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
        )

        state["workflow_status"] = "ship_pending"
        workflow_lib.save_state(state, state_path)
        not_committed = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert wrong_status.returncode != 0
    assert "workflow_status ship_pending" in wrong_status.stderr
    assert not_committed.returncode != 0
    assert "current step to be committed" in not_committed.stderr
    assert persisted_state["steps"][0]["status"] == "implementing"


def test_next_stop_decision_requires_explicit_completion_after_shipped_step():
    workflow_lib = load_workflow_lib()
    state = workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md")
    state["workflow_status"] = "ship_pending"
    state["steps"][0]["status"] = "shipped"

    next_state, decision, changed = workflow_lib.next_stop_decision(state)

    assert changed is False
    assert next_state["workflow_status"] == "ship_pending"
    assert decision.action == "block"
    assert "set-workflow-status complete" in (decision.prompt or "")
