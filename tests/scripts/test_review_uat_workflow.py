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
    scope_reviewed_paths: list[str] | None = None,
    verification_status: str = "passed",
    verification_note: str | None = None,
    verification_commands: list[str] | None = None,
    residual_testing_gaps: list[str] | None = None,
    agents_checked: list[str] | None = None,
    agents_updated: bool = False,
    review_findings: list[dict[str, object]] | None = None,
    finding_count: int,
) -> tuple[str, ...]:
    args = [
        "--review-summary",
        summary,
        "--scope-confirmed",
        "true" if scope_confirmed else "false",
    ]
    if scope_reviewed_paths is None and scope_confirmed:
        scope_reviewed_paths = [
            "app/ai/embedding/service.py",
            "tests/ai/test_embedding_service.py",
        ]
    for path in scope_reviewed_paths or []:
        args.extend(["--scope-reviewed-path", path])
    args.extend(["--verification-status", verification_status])
    if verification_note is not None:
        args.extend(["--verification-note", verification_note])
    if verification_commands is None and verification_status == "passed":
        verification_commands = ["uv run pytest tests/ai/test_embedding_service.py"]
    for command in verification_commands or []:
        args.extend(["--verification-command", command])
    if residual_testing_gaps is None and finding_count == 0:
        residual_testing_gaps = ["none noted"]
    for gap in residual_testing_gaps or []:
        args.extend(["--residual-testing-gap", gap])
    for path in agents_checked or ["AGENTS.md"]:
        args.extend(["--agents-checked", path])
    if review_findings is None and finding_count > 0:
        review_findings = [
            {
                "severity": "P2",
                "path": "app/ai/embedding/service.py",
                "summary": f"Material review finding {index}",
            }
            for index in range(1, finding_count + 1)
        ]
    for finding in review_findings or []:
        args.extend(["--review-finding", json.dumps(finding)])
    args.extend(
        [
            "--agents-updated",
            "true" if agents_updated else "false",
            "--finding-count",
            str(finding_count),
        ]
    )
    return tuple(args)


def _ship_args(
    *,
    branch: str = "feature/reconciled-ship",
    pr_url: str = "https://github.com/example/repo/pull/123",
    codex_review_status: str = "clean",
    state_memory_status: str = "updated",
    state_memory_summary: str = "STATE.md records the shipped PR handoff.",
) -> tuple[str, ...]:
    return (
        "--branch",
        branch,
        "--pr-url",
        pr_url,
        "--codex-review-status",
        codex_review_status,
        "--state-memory-status",
        state_memory_status,
        "--state-memory-summary",
        state_memory_summary,
    )


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
    assert "--scope-reviewed-path app/example/module.py" in decision.prompt
    assert "--verification-command 'uv run pytest tests/example/test_module.py'" in decision.prompt
    assert "--residual-testing-gap 'none noted'" in decision.prompt
    assert "--agents-checked AGENTS.md" in decision.prompt
    assert "--review-finding" in decision.prompt
    assert "one structured `--review-finding` JSON object per material finding" in decision.prompt
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
    assert "Passing reviews record residual testing gaps" in decision.prompt
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


def test_workflow_state_review_pending_accepts_validation_ownership_for_cross_step_target():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["file_ownership"] = ["app/ai/embedding/service.py"]
        state["steps"][0]["validation_ownership"] = ["tests/contracts/test_embedding_contract.py"]
        state["steps"][0]["verification_targets"] = ["tests/contracts/test_embedding_contract.py"]
        state["steps"][0]["verify_cmds"] = ["uv run pytest tests/contracts/test_embedding_contract.py"]
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


def test_workflow_state_review_pending_rejects_undeclared_cross_step_verification_target():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["steps"][0]["file_ownership"] = ["app/ai/embedding/service.py"]
        state["steps"][0]["verification_targets"] = ["tests/contracts/test_embedding_contract.py"]
        state["steps"][0]["verify_cmds"] = ["uv run pytest tests/contracts/test_embedding_contract.py"]
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "review_pending",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "file or validation ownership" in result.stderr
    assert persisted_state["workflow_status"] == "execution_escalated"
    assert persisted_state["steps"][0]["status"] == "implementing"
    assert persisted_state["escalation"]["code"] == "ownership_mismatch"


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


def test_workflow_state_commit_pending_rejected_without_scope_reviewed_path():
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
                scope_reviewed_paths=[],
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "--scope-reviewed-path" in result.stderr


def test_workflow_state_commit_pending_rejected_when_scope_reviewed_path_is_out_of_scope():
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
                scope_reviewed_paths=["app/unrelated/module.py"],
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "outside the step review scope" in result.stderr
    assert "app/unrelated/module.py" in result.stderr


def test_workflow_state_commit_pending_rejects_pseudo_child_under_file_scope():
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
                scope_reviewed_paths=["app/ai/embedding/service.py/not-real-child"],
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "outside the step review scope" in result.stderr
    assert "app/ai/embedding/service.py/not-real-child" in result.stderr


def test_workflow_state_commit_pending_rejects_pseudo_child_under_extensionless_file_scope():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)
        state = workflow_lib.load_state(state_path)
        state["steps"][0]["file_ownership"] = ["BUILD"]
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(
                summary="review passed",
                scope_reviewed_paths=["BUILD/not-real-child"],
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "outside the step review scope" in result.stderr
    assert "BUILD/not-real-child" in result.stderr


def test_workflow_state_commit_pending_rejects_pseudo_child_under_dotfile_scope():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)
        state = workflow_lib.load_state(state_path)
        state["steps"][0]["file_ownership"] = [".env"]
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(
                summary="review passed",
                scope_reviewed_paths=[".env/not-real-child"],
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "outside the step review scope" in result.stderr
    assert ".env/not-real-child" in result.stderr


def test_workflow_state_commit_pending_accepts_child_path_under_directory_scope():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)
        state = workflow_lib.load_state(state_path)
        state["steps"][0]["file_ownership"] = [".codex/workflow"]
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(
                summary="review passed",
                scope_reviewed_paths=[".codex/workflow/scripts/workflow_lib.py"],
                finding_count=0,
            ),
        )

    assert result.returncode == 0, result.stderr


def test_review_prompt_uses_agents_path_for_empty_step_scope_defaults():
    workflow_lib = load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    step = state["steps"][0]
    step["status"] = "review_pending"
    step["context"] = []
    step["verification_targets"] = []
    step["file_ownership"] = []
    step["validation_ownership"] = []
    step["agents_paths"] = ["AGENTS.md"]

    _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert decision.action == "block"
    assert "--scope-reviewed-path AGENTS.md" in decision.prompt


def test_legacy_review_record_backfills_agents_path_for_empty_step_scope_defaults():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        step = state["steps"][0]
        step["context"] = []
        step["verification_targets"] = []
        step["file_ownership"] = []
        step["validation_ownership"] = []
        step["agents_paths"] = ["AGENTS.md"]
        step["status"] = "commit_pending"
        step["review_summary"] = "review passed"
        step["review_record"] = {
            "outcome": "passed",
            "summary": "review passed",
            "scope_confirmed": True,
            "verification_status": "passed",
            "verification_note": None,
            "verification_commands": ["uv run pytest tests/ai/test_embedding_service.py"],
            "agents_checked": ["AGENTS.md"],
            "agents_updated": False,
            "finding_count": 0,
            "checked_at": "2026-01-01T00:00:00Z",
        }
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        persisted_state = workflow_lib.load_state(state_path)

    assert persisted_state["steps"][0]["review_record"]["scope_reviewed_paths"] == ["AGENTS.md"]
    assert persisted_state["steps"][0]["review_record"]["findings"] == []
    assert persisted_state["steps"][0]["review_record"]["residual_testing_gaps"] == [
        "not recorded; legacy review record predates residual testing gap evidence"
    ]


def test_legacy_failed_review_record_backfills_structured_findings():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        step = state["steps"][0]
        step["status"] = "fix_pending"
        step["review_summary"] = "Missing regression assertion."
        step["review_record"] = {
            "outcome": "failed",
            "summary": "Missing regression assertion.",
            "scope_confirmed": True,
            "scope_reviewed_paths": [
                "app/ai/embedding/service.py",
                "tests/ai/test_embedding_service.py",
            ],
            "verification_status": "passed",
            "verification_note": None,
            "verification_commands": ["uv run pytest tests/ai/test_embedding_service.py"],
            "agents_checked": ["AGENTS.md"],
            "agents_updated": False,
            "finding_count": 1,
            "checked_at": "2026-01-01T00:00:00Z",
        }
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        persisted_state = workflow_lib.load_state(state_path)

    assert persisted_state["steps"][0]["review_record"]["findings"] == [
        {
            "severity": "P2",
            "summary": "Missing regression assertion.",
            "no_path_reason": "legacy review record predates structured finding evidence",
        }
    ]
    assert persisted_state["steps"][0]["review_record"]["residual_testing_gaps"] == []


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


def test_workflow_state_commit_pending_rejected_without_verification_command_evidence():
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
                verification_commands=[],
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "--verification-command" in result.stderr


def test_workflow_state_commit_pending_rejected_when_verification_command_omits_verify_cmd():
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
                verification_commands=["uv run pytest tests/other.py"],
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "must include every verify_cmd" in result.stderr
    assert "uv run pytest tests/ai/test_embedding_service.py" in result.stderr


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


def test_workflow_state_commit_pending_rejected_without_residual_testing_gap_evidence():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(
                summary="No material findings.",
                residual_testing_gaps=[],
                finding_count=0,
            ),
        )

    assert result.returncode != 0
    assert "--residual-testing-gap" in result.stderr


def test_workflow_state_commit_pending_persists_residual_testing_gap_evidence():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "commit_pending",
            *_review_args(
                summary="No material findings.",
                residual_testing_gaps=["only focused step tests ran"],
                finding_count=0,
            ),
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode == 0, result.stderr
    assert persisted_state["steps"][0]["review_record"]["residual_testing_gaps"] == [
        "only focused step tests ran"
    ]


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


def test_workflow_state_fix_pending_rejected_without_structured_finding_evidence():
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
                review_findings=[],
                finding_count=1,
            ),
        )

    assert result.returncode != 0
    assert "--review-finding" in result.stderr


def test_workflow_state_fix_pending_rejected_when_finding_path_is_out_of_scope():
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
                review_findings=[
                    {
                        "severity": "P2",
                        "path": "app/unrelated/module.py",
                        "summary": "Finding path is outside the reviewed step scope.",
                    }
                ],
                finding_count=1,
            ),
        )

    assert result.returncode != 0
    assert "outside the step review scope" in result.stderr
    assert "app/unrelated/module.py" in result.stderr


def test_workflow_state_fix_pending_rejected_when_findings_are_not_severity_ordered():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "fix_pending",
            *_review_args(
                summary="Review findings are not ordered by severity.",
                review_findings=[
                    {
                        "severity": "P3",
                        "path": "app/ai/embedding/service.py",
                        "summary": "Lower severity finding appears first.",
                    },
                    {
                        "severity": "P1",
                        "path": "tests/ai/test_embedding_service.py",
                        "summary": "Higher severity finding appears second.",
                    },
                ],
                finding_count=2,
            ),
        )

    assert result.returncode != 0
    assert "ordered by severity" in result.stderr


def test_workflow_state_fix_pending_accepts_finding_with_no_file_reference_reason():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _prepare_review_pending_state(workflow_lib, tmpdir)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "fix_pending",
            *_review_args(
                summary="Verification was blocked before a file-specific finding.",
                verification_status="blocked",
                verification_note="Required local service was unavailable.",
                review_findings=[
                    {
                        "severity": "P2",
                        "summary": "Verification could not run to completion.",
                        "no_path_reason": "blocked verification has no file-specific location",
                    }
                ],
                finding_count=1,
            ),
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode == 0, result.stderr
    assert persisted_state["steps"][0]["review_record"]["findings"] == [
        {
            "severity": "P2",
            "summary": "Verification could not run to completion.",
            "no_path_reason": "blocked verification has no file-specific location",
        }
    ]


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
    assert review_record["scope_reviewed_paths"] == [
        "app/ai/embedding/service.py",
        "tests/ai/test_embedding_service.py",
    ]
    assert review_record["verification_status"] == "passed"
    assert review_record["verification_note"] is None
    assert review_record["verification_commands"] == ["uv run pytest tests/ai/test_embedding_service.py"]
    assert review_record["residual_testing_gaps"] == []
    assert review_record["agents_checked"] == ["AGENTS.md"]
    assert review_record["agents_updated"] is False
    assert review_record["findings"] == [
        {
            "severity": "P2",
            "summary": "Material review finding 1",
            "path": "app/ai/embedding/service.py",
        },
        {
            "severity": "P2",
            "summary": "Material review finding 2",
            "path": "app/ai/embedding/service.py",
        },
    ]
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
    assert review_record["findings"] == []
    assert review_record["scope_reviewed_paths"] == [
        "app/ai/embedding/service.py",
        "tests/ai/test_embedding_service.py",
    ]
    assert review_record["verification_status"] == "passed"
    assert review_record["verification_commands"] == ["uv run pytest tests/ai/test_embedding_service.py"]
    assert review_record["residual_testing_gaps"] == ["none noted"]


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


def test_workflow_state_loads_legacy_state_without_ship_record():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        del state["ship_record"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        persisted_state = workflow_lib.load_state(state_path)

    assert persisted_state["ship_record"] is None


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


def test_workflow_state_set_step_status_shipped_records_ship_handoff():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state_memory_path = Path(tmpdir) / "STATE.md"
        state_memory_path.write_text(
            "# State\n\n## Workflow Status\n- PR opened and ready for workflow completion.\n",
            encoding="utf-8",
        )
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(
            workflow_lib,
            state,
            state_memory_path=str(state_memory_path),
        )

        uat_result = run_workflow_state_command(
            state_path,
            "set-uat-status",
            "passed",
            "--summary",
            "UAT passed and repo memory was reconciled.",
        )
        ship_result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
            *_ship_args(),
        )
        complete_result = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "complete",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert uat_result.returncode == 0, uat_result.stderr
    assert ship_result.returncode == 0, ship_result.stderr
    assert complete_result.returncode == 0, complete_result.stderr
    assert persisted_state["workflow_status"] == "complete"
    assert persisted_state["ship_record"]["step_id"] == "step-1"
    assert persisted_state["ship_record"]["pr_url"] == "https://github.com/example/repo/pull/123"
    assert persisted_state["ship_record"]["state_memory_status"] == "updated"


def test_workflow_state_complete_requires_ship_record():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "ship_pending"
        state["steps"][0]["status"] = "shipped"
        workflow_lib.save_state(state, state_path)

        result = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "complete",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "ship_record is missing" in result.stderr
    assert persisted_state["workflow_status"] == "ship_pending"


def test_workflow_state_complete_rejects_state_memory_drift_after_ship_record():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state_memory_path = Path(tmpdir) / "STATE.md"
        state_memory_path.write_text(
            "# State\n\n## Workflow Status\n- PR opened and ready for workflow completion.\n",
            encoding="utf-8",
        )
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(
            workflow_lib,
            state,
            state_memory_path=str(state_memory_path),
        )

        uat_result = run_workflow_state_command(
            state_path,
            "set-uat-status",
            "passed",
            "--summary",
            "UAT passed.",
        )
        ship_result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
            *_ship_args(state_memory_summary="STATE.md was verified before PR completion."),
        )
        state_memory_path.write_text(
            "# State\n\n## Workflow Status\n- Execution in progress.\n",
            encoding="utf-8",
        )
        complete_result = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "complete",
        )
        state_memory_path.write_text(
            "# State\n\n## Workflow Status\n- PR opened and ready for workflow completion after reconciliation.\n",
            encoding="utf-8",
        )
        refresh_result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
            *_ship_args(state_memory_summary="STATE.md was refreshed after drift."),
        )
        final_complete_result = run_workflow_state_command(
            state_path,
            "set-workflow-status",
            "complete",
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert uat_result.returncode == 0, uat_result.stderr
    assert ship_result.returncode == 0, ship_result.stderr
    assert complete_result.returncode != 0
    assert "STATE.md changed after ship_record was recorded" in complete_result.stderr
    assert refresh_result.returncode == 0, refresh_result.stderr
    assert final_complete_result.returncode == 0, final_complete_result.stderr
    assert persisted_state["workflow_status"] == "complete"


def test_workflow_state_shipped_requires_uat_metrics_reconciliation():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state_memory_path = Path(tmpdir) / "STATE.md"
        state_memory_path.write_text(
            "# State\n\n## Workflow Status\n- PR opened and ready for workflow completion.\n",
            encoding="utf-8",
        )
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "ship_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(
            workflow_lib,
            state,
            state_memory_path=str(state_memory_path),
        )
        workflow_lib.update_uat_artifact_result(
            Path(state["uat_artifact_path"]),
            "passed",
            "UAT was marked passed without a matching metrics event.",
        )

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
            *_ship_args(),
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "metrics are missing a uat_passed event" in result.stderr
    assert persisted_state["steps"][0]["status"] == "committed"
    assert persisted_state["ship_record"] is None


def test_workflow_state_shipped_rejects_state_memory_directory_without_traceback():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(
            workflow_lib,
            state,
            state_memory_path=tmpdir,
        )

        uat_result = run_workflow_state_command(
            state_path,
            "set-uat-status",
            "passed",
            "--summary",
            "UAT passed with a malformed state memory path.",
        )
        ship_result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
            *_ship_args(),
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert uat_result.returncode == 0, uat_result.stderr
    assert ship_result.returncode != 0
    assert "STATE.md reconciliation path is not a file" in ship_result.stderr
    assert "Traceback" not in ship_result.stderr
    assert persisted_state["steps"][0]["status"] == "committed"
    assert persisted_state["ship_record"] is None


def test_workflow_state_shipped_rejects_metrics_directory_without_traceback():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state_memory_path = Path(tmpdir) / "STATE.md"
        state_memory_path.write_text(
            "# State\n\n## Workflow Status\n- PR opened and ready for workflow completion.\n",
            encoding="utf-8",
        )
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "ship_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(
            workflow_lib,
            state,
            state_memory_path=str(state_memory_path),
        )
        workflow_lib.update_uat_artifact_result(
            Path(state["uat_artifact_path"]),
            "passed",
            "UAT was marked passed before metrics-log corruption.",
        )
        events_path = Path(state["metrics_dir"]) / "events.jsonl"
        events_path.mkdir(parents=True)

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
            *_ship_args(),
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "metrics event log could not be read" in result.stderr
    assert "Traceback" not in result.stderr
    assert persisted_state["steps"][0]["status"] == "committed"
    assert persisted_state["ship_record"] is None


def test_workflow_state_shipped_ignores_stale_uat_passed_metric_from_prior_run():
    workflow_lib = load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state_memory_path = Path(tmpdir) / "STATE.md"
        state_memory_path.write_text(
            "# State\n\n## Workflow Status\n- PR opened and ready for workflow completion.\n",
            encoding="utf-8",
        )
        state = _build_execution_state(workflow_lib, tmpdir)
        state["workflow_status"] = "ship_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        save_example_uat_artifact(
            workflow_lib,
            state,
            state_memory_path=str(state_memory_path),
        )
        workflow_lib.update_uat_artifact_result(
            Path(state["uat_artifact_path"]),
            "passed",
            "UAT artifact was passed but current-run metrics were not written.",
        )
        metrics_dir = Path(state["metrics_dir"])
        metrics_dir.mkdir(parents=True, exist_ok=True)
        events_path = metrics_dir / "events.jsonl"
        events_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "event": "uat_passed",
                            "timestamp": "2026-01-01T00:00:00Z",
                            "workflow_name": state["workflow_name"],
                            "current_step_id": state["current_step_id"],
                        }
                    ),
                    json.dumps(
                        {
                            "event": "execution_activated",
                            "timestamp": "2026-01-01T00:01:00Z",
                            "workflow_name": state["workflow_name"],
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = run_workflow_state_command(
            state_path,
            "set-step-status",
            "step-1",
            "shipped",
            *_ship_args(),
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert result.returncode != 0
    assert "metrics are missing a uat_passed event" in result.stderr
    assert persisted_state["steps"][0]["status"] == "committed"
    assert persisted_state["ship_record"] is None


def test_next_stop_decision_requires_handoff_reconciliation_after_shipped_step():
    workflow_lib = load_workflow_lib()
    state = workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md")
    state["workflow_status"] = "ship_pending"
    state["steps"][0]["status"] = "shipped"

    next_state, decision, changed = workflow_lib.next_stop_decision(state)

    assert changed is False
    assert next_state["workflow_status"] == "ship_pending"
    assert decision.action == "block"
    assert "ship handoff reconciliation" in (decision.prompt or "")
    assert "set-step-status step-1 shipped --branch" in (decision.prompt or "")
    assert "set-workflow-status complete" in (decision.prompt or "")
