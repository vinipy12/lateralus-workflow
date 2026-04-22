from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / ".codex" / "workflow" / "scripts"
WORKFLOW_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "workflow_lib.py"
PLANNING_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "planning_lib.py"
USER_PROMPT_HOOK_PATH = WORKFLOW_SCRIPTS_DIR / "user_prompt_hook.py"
WORKFLOW_ROUTER_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "workflow_router_lib.py"
WORKFLOW_STATE_CLI_PATH = WORKFLOW_SCRIPTS_DIR / "workflow_state.py"
METRICS_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "metrics_lib.py"
STATE_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "state.example.json"
PLANNING_STATE_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "planning_state.example.json"
PLAN_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "plan.example.json"
README_PATH = REPO_ROOT / "README.md"
NEXT_STEPS_PATH = REPO_ROOT / "next-steps.md"
WORKFLOW_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "SKILL.md"
WORKFLOW_SKILL_OPENAI_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "agents" / "openai.yaml"
WORKFLOW_ROUTER_SKILL_SCRIPT_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "scripts" / "workflow_router.py"
PLANNING_STATE_SKILL_SCRIPT_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "scripts" / "planning_state.py"
WORKFLOW_STATE_SKILL_SCRIPT_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "scripts" / "workflow_state.py"
SHIP_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "ship" / "SKILL.md"
SHIP_WORKFLOW_STATE_SKILL_SCRIPT_PATH = REPO_ROOT / ".agents" / "skills" / "ship" / "scripts" / "workflow_state.py"
PLUGIN_MANIFEST_PATH = REPO_ROOT / ".codex-plugin" / "plugin.json"


if str(WORKFLOW_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS_DIR))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_workflow_lib():
    return _load_module("codex_workflow_lib", WORKFLOW_LIB_PATH)


def _load_planning_lib():
    return _load_module("codex_planning_lib", PLANNING_LIB_PATH)


def _load_user_prompt_hook():
    return _load_module("codex_user_prompt_hook", USER_PROMPT_HOOK_PATH)


def _load_workflow_router_lib():
    return _load_module("codex_workflow_router_lib", WORKFLOW_ROUTER_LIB_PATH)


def _load_metrics_lib():
    return _load_module("codex_metrics_lib", METRICS_LIB_PATH)


def _example_plan() -> dict:
    return {
        "workflow_name": "Embedding change",
        "summary": "Update the embedding flow in one verified step.",
        "requirements": [
            {"id": "R1", "text": "Update the embedding behavior."},
            {"id": "R2", "kind": "verification", "text": "Verify the embedding behavior with a targeted test."},
        ],
        "assumptions": [],
        "open_questions": [],
        "out_of_scope": [],
        "steps": [
            {
                "title": "Adjust embedding behavior",
                "goal": "Update the embedding flow.",
                "requirement_ids": ["R1", "R2"],
                "context": ["app/ai/embedding/service.py"],
                "planned_updates": ["app/ai/embedding/service.py"],
                "planned_creates": [],
                "constraints": ["Keep the change scoped to the embedding service."],
                "justification": "This keeps the change isolated to the embedding service.",
                "files_read_first": ["app/ai/embedding/service.py"],
                "interfaces_to_preserve": ["Embedding service public behavior"],
                "avoid_touching": ["app/api/embedding.py"],
                "verification_targets": ["tests/ai/test_embedding_service.py"],
                "risk_flags": ["Preserve existing embedding output shape for current consumers."],
                "blast_radius": ["app/ai/embedding/service.py consumers"],
                "decision_ids": ["D-EMBED-1"],
                "depends_on": [],
                "wave": 1,
                "file_ownership": [
                    "app/ai/embedding/service.py",
                    "tests/ai/test_embedding_service.py",
                ],
                "rollback_notes": [
                    "Revert the embedding behavior commit if current consumers regress.",
                ],
                "operational_watchpoints": [
                    "Watch the embedding service public behavior contract during verification.",
                ],
                "done_when": ["The embedding flow uses the updated behavior."],
                "verify_cmds": ["uv run pytest tests/ai/test_embedding_service.py"],
                "commit_message": "feature: adjust embedding behavior",
            }
        ],
    }


def _write_supporting_planning_artifacts(
    state: dict,
    *,
    preserved_interfaces: list[str] | None = None,
    project_constraints: list[str] | None = None,
    deferred: list[str] | None = None,
    open_questions: list[str] | None = None,
    active_initiative: str | None = None,
    product_scope_recommendation: str = "pass",
    skeptic_recommendation: str = "pass",
    unresolved_objections: list[str] | None = None,
) -> None:
    feature_request = state["feature_request"]
    Path(state["context_path"]).write_text(
        json.dumps(
            {
                "version": 1,
                "feature_request": feature_request,
                "goal": "Ship a decision-complete plan.",
                "target_user": "Workflow maintainers",
                "desired_behavior": "The planner should produce a safe, implementable plan.",
                "good_outcomes": ["The implementer can follow the plan directly."],
                "bad_outcomes": ["The plan leaves architecture or verification decisions open."],
                "locked_decisions": ["Keep planning artifacts JSON-first."],
                "defaults_taken": ["Prefer the smallest viable slice."],
                "open_questions": open_questions or [],
                "constraints": ["Do not implement code during planning."],
                "success_criteria": ["The approved plan is audit-clean."],
                "non_goals": ["Execution-phase work."],
                "unresolved_risks": [],
            }
        ),
        encoding="utf-8",
    )
    Path(state["scope_contract_path"]).write_text(
        json.dumps(
            {
                "version": 1,
                "feature_request": feature_request,
                "must_have": ["Produce an approval-ready plan."],
                "deferred": deferred or [],
                "non_goals": ["Unrelated cleanup."],
                "success_criteria": ["The plan is specific enough for another agent to implement."],
                "mvp_boundary": "Only planning artifacts and plan quality improvements are in scope.",
                "defaults_taken": ["Use direct verification targets."],
            }
        ),
        encoding="utf-8",
    )
    Path(state["architecture_constraints_path"]).write_text(
        json.dumps(
            {
                "version": 1,
                "feature_request": feature_request,
                "required_reuse": ["Existing workflow state management."],
                "approved_patterns": ["Repo-local JSON artifacts."],
                "forbidden_moves": ["Do not invent a new runtime just for planning."],
                "preserved_interfaces": preserved_interfaces or ["Existing workflow entrypoints"],
                "migration_constraints": ["Keep `$workflow` as the main trigger."],
                "architecture_risks": [],
            }
        ),
        encoding="utf-8",
    )
    Path(state["product_scope_audit_path"]).write_text(
        json.dumps(
            {
                "version": 1,
                "feature_request": feature_request,
                "included_scope": ["Produce an approval-ready plan."],
                "deferred_scope": deferred or [],
                "defaults_taken": ["Use direct verification targets."],
                "unresolved_risks": [],
                "recommendation": product_scope_recommendation,
            }
        ),
        encoding="utf-8",
    )
    Path(state["skeptic_audit_path"]).write_text(
        json.dumps(
            {
                "version": 1,
                "feature_request": feature_request,
                "objections": [],
                "unresolved_objections": unresolved_objections or [],
                "recommendation": skeptic_recommendation,
            }
        ),
        encoding="utf-8",
    )
    Path(state["convergence_summary_path"]).write_text(
        json.dumps(
            {
                "version": 1,
                "feature_request": feature_request,
                "included_scope": ["Produce an approval-ready plan."],
                "deferred_scope": deferred or [],
                "defaults_taken": ["Use direct verification targets."],
                "unresolved_risks": [],
                "approval_summary": "The plan is scoped, audited, and ready for approval.",
            }
        ),
        encoding="utf-8",
    )
    Path(state["project_memory_path"]).write_text(
        "\n".join(
            [
                "# Project",
                "",
                "## Product Intent",
                "- Build an auditable workflow kernel.",
                "",
                "## Target Users",
                "- Workflow maintainers.",
                "",
                "## Durable Constraints",
                *[
                    f"- {item}"
                    for item in (
                        project_constraints
                        or preserved_interfaces
                        or ["Existing workflow entrypoints"]
                    )
                ],
                "",
                "## Strategy",
                "- Stabilize the kernel before packaging.",
                "",
                "## Current Priorities",
                "- Produce an approval-ready plan.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    Path(state["requirements_memory_path"]).write_text(
        "\n".join(
            [
                "# Requirements",
                "",
                "## Active Backlog",
                "- Produce an approval-ready plan.",
                "",
                "## Accepted Requirements",
                "- The approved plan is audit-clean.",
                "",
                "## Deferred Scope",
                *[f"- {item}" for item in (deferred or ["Unrelated cleanup."])],
                "",
                "## Milestone Commitments",
                "- Keep planning artifacts JSON-first.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    Path(state["state_memory_path"]).write_text(
        "\n".join(
            [
                "# State",
                "",
                "## Workflow Status",
                "- Planning in progress.",
                "",
                "## Active Initiative",
                f"- {active_initiative or 'Produce an approval-ready plan.'}",
                "",
                "## Latest Decisions",
                "- Keep planning artifacts JSON-first.",
                "",
                "## Release State",
                "- Pre-approval.",
                "",
                "## Unresolved Risks",
                "- None.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _rebase_planning_state_paths(state: dict, tmpdir: str) -> dict:
    tmp_root = Path(tmpdir)
    rebased = dict(state)
    rebased["approved_plan_path"] = str(tmp_root / "approved-plan.json")
    rebased["context_path"] = str(tmp_root / "context.json")
    rebased["discovery_dossier_path"] = str(tmp_root / "discovery_dossier.json")
    rebased["scope_contract_path"] = str(tmp_root / "scope_contract.json")
    rebased["architecture_constraints_path"] = str(tmp_root / "architecture_constraints.json")
    rebased["product_scope_audit_path"] = str(tmp_root / "product_scope_audit.json")
    rebased["skeptic_audit_path"] = str(tmp_root / "skeptic_audit.json")
    rebased["convergence_summary_path"] = str(tmp_root / "convergence_summary.json")
    rebased["stack_runtime_decision_path"] = str(tmp_root / "stack_runtime_decision.json")
    rebased["bootstrap_expectations_path"] = str(tmp_root / "bootstrap_expectations.json")
    rebased["planning_trace_path"] = str(tmp_root / "planning_trace.json")
    rebased["project_memory_path"] = str(tmp_root / "PROJECT.md")
    rebased["requirements_memory_path"] = str(tmp_root / "REQUIREMENTS.md")
    rebased["state_memory_path"] = str(tmp_root / "STATE.md")
    return rebased


def _rebase_execution_state_paths(state: dict, tmpdir: str) -> dict:
    tmp_root = Path(tmpdir)
    rebased = deepcopy(state)
    rebased["uat_artifact_path"] = str(tmp_root / "uat.json")
    rebased["metrics_dir"] = str(tmp_root / "metrics")
    return rebased


def _write_greenfield_planning_artifacts(state: dict) -> None:
    Path(state["stack_runtime_decision_path"]).write_text(
        json.dumps(
            {
                "version": 1,
                "feature_request": state["feature_request"],
                "runtime_language_choice": "Python 3.13",
                "framework_choice": "Repo-local CLI scripts",
                "storage_choice": "JSON artifacts on disk",
                "rationale": [
                    "Match the existing workflow kernel runtime.",
                    "Keep the bootstrap deterministic and auditable.",
                ],
                "unresolved_questions": [],
            }
        ),
        encoding="utf-8",
    )
    Path(state["bootstrap_expectations_path"]).write_text(
        json.dumps(
            {
                "version": 1,
                "feature_request": state["feature_request"],
                "ci_testing_baseline_expectations": [
                    "Focused pytest coverage must exist before approval.",
                ],
                "deployment_release_baseline_expectations": [
                    "Shipping must still go through the repo-local publish flow.",
                ],
            }
        ),
        encoding="utf-8",
    )


def test_example_state_is_valid():
    workflow_lib = _load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    workflow_lib.validate_state(state)


def test_example_planning_state_is_valid():
    planning_lib = _load_planning_lib()
    state = json.loads(PLANNING_STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    planning_lib.validate_planning_state(state)


def test_build_planning_state_starts_in_discuss():
    planning_lib = _load_planning_lib()

    state = planning_lib.build_planning_state("Plan an improved workflow")

    assert state["status"] == "discuss"
    assert state["planning_mode"] == "brownfield"
    assert state["phase_checkpoint"] == "discuss"
    assert state["context_path"].endswith("context.json")
    assert state["scope_contract_path"].endswith("scope_contract.json")
    assert state["architecture_constraints_path"].endswith("architecture_constraints.json")
    assert state["stack_runtime_decision_path"].endswith("stack_runtime_decision.json")
    assert state["bootstrap_expectations_path"].endswith("bootstrap_expectations.json")
    assert state["project_memory_path"] == "PROJECT.md"
    assert state["requirements_memory_path"] == "REQUIREMENTS.md"
    assert state["state_memory_path"] == "STATE.md"


def test_load_planning_state_backfills_v0_paths():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        planning_state_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "status": "approval_ready",
                    "feature_request": "Preserve the old planning session",
                    "approved_plan_path": ".codex/workflow/approved-plan.json",
                    "discovery_dossier_path": ".codex/workflow/discovery_dossier.json",
                    "planning_trace_path": ".codex/workflow/planning_trace.json",
                    "clarifying_question_limit": 3,
                    "discovery_callback_limit": 2,
                    "revision_count": 0,
                    "latest_user_feedback": None,
                }
            ),
            encoding="utf-8",
        )

        state = planning_lib.load_planning_state(planning_state_path)

    assert state is not None
    assert state["context_path"].endswith("context.json")
    assert state["scope_contract_path"].endswith("scope_contract.json")
    assert state["architecture_constraints_path"].endswith("architecture_constraints.json")
    assert state["product_scope_audit_path"].endswith("product_scope_audit.json")
    assert state["skeptic_audit_path"].endswith("skeptic_audit.json")
    assert state["convergence_summary_path"].endswith("convergence_summary.json")
    assert state["stack_runtime_decision_path"].endswith("stack_runtime_decision.json")
    assert state["bootstrap_expectations_path"].endswith("bootstrap_expectations.json")
    assert state["project_memory_path"].endswith("PROJECT.md")
    assert state["requirements_memory_path"].endswith("REQUIREMENTS.md")
    assert state["state_memory_path"].endswith("STATE.md")
    assert state["phase_checkpoint"] == "approval_ready"
    assert state["planning_mode"] == "brownfield"


def test_load_planning_state_inferrs_checkpoint_for_legacy_revising_session():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        state = _rebase_planning_state_paths(
            planning_lib.build_planning_state("Revise an in-flight planning session"),
            tmpdir,
        )
        planning_lib.initialize_planning_artifacts(state)
        Path(state["approved_plan_path"]).write_text(json.dumps(_example_plan()), encoding="utf-8")
        legacy_state = dict(state)
        legacy_state["status"] = "revising"
        legacy_state.pop("phase_checkpoint", None)
        planning_state_path = tmp_root / "planning_state.json"
        planning_state_path.write_text(json.dumps(legacy_state), encoding="utf-8")

        loaded_state = planning_lib.load_planning_state(planning_state_path)

    assert loaded_state is not None
    assert loaded_state["status"] == "revising"
    assert loaded_state["phase_checkpoint"] == "planning"


def test_planning_phase_advance_rejects_incomplete_discuss_outputs():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_planning_state_paths(
            planning_lib.build_planning_state("Plan a gated workflow"),
            tmpdir,
        )
        planning_lib.initialize_planning_artifacts(state)

        try:
            planning_lib.advance_planning_phase(state, target_status="discovery")
        except ValueError as exc:
            assert "cannot advance planning phase from `discuss`" in str(exc)
            assert "context.goal" in str(exc)
        else:
            raise AssertionError("expected discuss phase advancement to reject incomplete artifacts")


def test_planning_phase_advance_accepts_repaired_discuss_outputs():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_planning_state_paths(
            planning_lib.build_planning_state("Plan a gated workflow"),
            tmpdir,
        )
        planning_lib.initialize_planning_artifacts(state)
        _write_supporting_planning_artifacts(
            state,
            active_initiative="Produce an approval-ready plan.",
        )

        advanced_state = planning_lib.advance_planning_phase(state, target_status="discovery")

    assert advanced_state["status"] == "discovery"
    assert advanced_state["phase_checkpoint"] == "discovery"


def test_blocked_planning_phase_stays_blocked_until_artifacts_are_repaired():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_planning_state_paths(
            planning_lib.set_planning_status(
                planning_lib.build_planning_state("Repair blocked planning"),
                "blocked",
            ),
            tmpdir,
        )
        planning_lib.initialize_planning_artifacts(state)

        try:
            planning_lib.advance_planning_phase(state, target_status="discovery")
        except ValueError as exc:
            assert "cannot advance planning phase from `discuss`" in str(exc)
        else:
            raise AssertionError("expected blocked planning to remain blocked without repaired artifacts")

        _write_supporting_planning_artifacts(
            state,
            active_initiative="Produce an approval-ready plan.",
        )
        advanced_state = planning_lib.advance_planning_phase(state, target_status="discovery")

    assert advanced_state["status"] == "discovery"
    assert advanced_state["phase_checkpoint"] == "discovery"


def test_example_plan_builds_valid_state():
    workflow_lib = _load_workflow_lib()
    plan = json.loads(PLAN_EXAMPLE_PATH.read_text(encoding="utf-8"))

    state = workflow_lib.build_state_from_plan_spec(plan, plan_path=".codex/workflow/plan.example.json")

    workflow_lib.validate_state(state)
    assert state["current_step_id"] == "step-1"
    assert state["steps"][0]["status"] == "implementing"
    assert state["steps"][1]["status"] == "pending"
    assert state["steps"][1]["commit_message"] == "feature: land the follow-up slice"
    assert state["steps"][0]["files_read_first"] == [
        "app/example/module.py",
        "tests/example/test_module.py",
    ]
    assert state["steps"][0]["risk_flags"] == ["Consumer behavior must remain stable for current callers."]
    assert state["steps"][0]["decision_ids"] == ["D-EXAMPLE-STEP-1"]
    assert state["steps"][0]["wave"] == 1
    assert state["steps"][1]["depends_on"] == ["step-1"]
    assert state["steps"][1]["file_ownership"] == [
        "app/example/second_module.py",
        "tests/example/test_second_module.py",
    ]
    assert state["uat_artifact_path"] == ".codex/workflow/uat.json"
    assert state["metrics_dir"] == ".codex/workflow/metrics"


def test_plan_inference_adds_relevant_agents_paths():
    workflow_lib = _load_workflow_lib()

    state = workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md")

    assert state["steps"][0]["agents_paths"] == ["AGENTS.md"]


def test_plan_validation_requires_requirement_coverage():
    workflow_lib = _load_workflow_lib()
    plan = _example_plan()
    plan["requirements"].append({"id": "R3", "text": "Uncovered requirement."})

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        try:
            workflow_lib.load_plan_spec(plan_path)
        except ValueError as exc:
            assert "requirements missing step coverage" in str(exc)
        else:
            raise AssertionError("expected load_plan_spec to reject uncovered requirements")


def test_plan_validation_rejects_boolean_wave_values():
    workflow_lib = _load_workflow_lib()
    plan = _example_plan()
    plan["steps"][0]["wave"] = True

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        try:
            workflow_lib.load_plan_spec(plan_path)
        except ValueError as exc:
            assert "wave must be a positive integer" in str(exc)
        else:
            raise AssertionError("expected load_plan_spec to reject boolean wave values")


def test_committed_step_advances_to_next_pending_step():
    workflow_lib = _load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["steps"][0]["status"] = "committed"

    new_state, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is True
    assert decision.action == "block"
    assert new_state["current_step_id"] == "step-2"
    assert new_state["steps"][1]["status"] == "implementing"
    assert "step-2" in decision.prompt


def test_review_pending_step_blocks_for_review_gate():
    workflow_lib = _load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["steps"][0]["status"] = "review_pending"

    _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert decision.action == "block"
    assert "code_review.md" in decision.prompt
    assert "python3 .codex/workflow/scripts/workflow_state.py set-step-status step-1 commit_pending" in decision.prompt
    assert "set-step-status step-1 commit_pending" in decision.prompt


def test_activation_prompt_renders_execution_handoff_fields():
    workflow_lib = _load_workflow_lib()
    state = workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md")

    prompt = workflow_lib.activation_prompt(state)

    assert "Justification:\nThis keeps the change isolated to the embedding service." in prompt
    assert "Files to read first:\n- app/ai/embedding/service.py" in prompt
    assert "Interfaces to preserve:\n- Embedding service public behavior" in prompt
    assert "Avoid touching:\n- app/api/embedding.py" in prompt
    assert "Verification targets:\n- tests/ai/test_embedding_service.py" in prompt
    assert "Risk flags:\n- Preserve existing embedding output shape for current consumers." in prompt
    assert "Blast radius:\n- app/ai/embedding/service.py consumers" in prompt
    assert "Decision IDs:\n- D-EMBED-1" in prompt
    assert "Wave:\n1" in prompt
    assert "Depends on:\n- none" not in prompt
    assert "Owned files:\n- app/ai/embedding/service.py" in prompt
    assert "Rollback notes:\n- Revert the embedding behavior commit if current consumers regress." in prompt
    assert "Operational watchpoints:\n- Watch the embedding service public behavior contract during verification." in prompt
    assert "Update `STATE.md`" in prompt


def test_final_committed_step_enters_uat_pending_mode():
    workflow_lib = _load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["current_step_id"] = "step-2"
    state["steps"][0]["status"] = "committed"
    state["steps"][1]["status"] = "committed"
    state["uat_artifact_path"] = str(REPO_ROOT / ".codex" / "workflow" / "uat.json")

    new_state, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is True
    assert new_state["workflow_status"] == "uat_pending"
    assert decision.action == "block"
    assert "set-uat-status passed" in decision.prompt


def test_uat_pending_blocks_with_uat_prompt():
    workflow_lib = _load_workflow_lib()
    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_uat_artifact(
            workflow_lib.build_uat_artifact(
                _example_plan(),
                workflow_name=state["workflow_name"],
                plan_path=state["plan_path"],
                project_memory_path="PROJECT.md",
                requirements_memory_path="REQUIREMENTS.md",
                state_memory_path="STATE.md",
            ),
            Path(state["uat_artifact_path"]),
        )

        _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert "user-acceptance gate" in decision.prompt
    assert "set-uat-status failed-gap" in decision.prompt


def test_gap_closure_pending_returns_to_uat_after_fix_commit():
    workflow_lib = _load_workflow_lib()
    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["workflow_status"] = "gap_closure_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_uat_artifact(
            workflow_lib.build_uat_artifact(
                _example_plan(),
                workflow_name=state["workflow_name"],
                plan_path=state["plan_path"],
                project_memory_path="PROJECT.md",
                requirements_memory_path="REQUIREMENTS.md",
                state_memory_path="STATE.md",
            ),
            Path(state["uat_artifact_path"]),
        )

        new_state, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is True
    assert new_state["workflow_status"] == "uat_pending"
    assert "set-uat-status passed" in decision.prompt


def test_replan_required_blocks_with_follow_up_planning_prompt():
    workflow_lib = _load_workflow_lib()
    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["workflow_status"] = "replan_required"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_uat_artifact(
            workflow_lib.build_uat_artifact(
                _example_plan(),
                workflow_name=state["workflow_name"],
                plan_path=state["plan_path"],
                project_memory_path="PROJECT.md",
                requirements_memory_path="REQUIREMENTS.md",
                state_memory_path="STATE.md",
            ),
            Path(state["uat_artifact_path"]),
        )
        workflow_lib.update_uat_artifact_result(
            Path(state["uat_artifact_path"]),
            "failed_replan",
            "The approved architecture no longer matches the required scope.",
        )

        _, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is False
    assert "cannot ship" in decision.prompt
    assert "follow-up planning session" in decision.prompt


def test_markdown_plan_file_can_be_selected_by_plan_id():
    workflow_lib = _load_workflow_lib()
    markdown = """
# Plans

```json
{
  "plan_id": "first",
  "workflow_name": "First plan",
  "summary": "Ship one.",
  "requirements": [
    {"id": "R1", "text": "Ship one."}
  ],
  "assumptions": [],
  "open_questions": [],
  "out_of_scope": [],
  "steps": [
    {
      "title": "One",
      "goal": "Ship one.",
      "requirement_ids": ["R1"],
      "context": ["app/example/one.py"],
      "planned_updates": ["app/example/one.py"],
      "planned_creates": [],
      "constraints": [],
      "done_when": ["One ships."],
      "verify_cmds": ["uv run pytest tests/example/test_one.py"],
      "commit_message": "feature: ship one"
    }
  ]
}
```

```json
{
  "plan_id": "second",
  "workflow_name": "Second plan",
  "summary": "Ship two.",
  "requirements": [
    {"id": "R1", "text": "Ship two."}
  ],
  "assumptions": [],
  "open_questions": [],
  "out_of_scope": [],
  "steps": [
    {
      "title": "Two",
      "goal": "Ship two.",
      "requirement_ids": ["R1"],
      "context": ["app/example/two.py"],
      "planned_updates": ["app/example/two.py"],
      "planned_creates": [],
      "constraints": [],
      "done_when": ["Two ships."],
      "verify_cmds": ["uv run pytest tests/example/test_two.py"],
      "commit_message": "feature: ship two"
    }
  ]
}
```
""".strip()
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "plans.md"
        plan_path.write_text(markdown, encoding="utf-8")

        plan = workflow_lib.load_plan_spec(plan_path, plan_id="second")

    assert plan["workflow_name"] == "Second plan"


def test_user_prompt_hook_parses_workflow_start_command():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_activation_request(
        "/workflow start PLANS.md --plan-id phase-1 --mode stepwise --base-branch origin/develop --no-request-codex-review"
    )

    assert request is not None
    assert str(request.source) == "PLANS.md"
    assert request.plan_id == "phase-1"
    assert request.mode == "stepwise"
    assert request.base_branch == "origin/develop"
    assert request.request_codex_review is False


def test_user_prompt_hook_parses_planning_request():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_workflow_request("/workflow add a planning phase for feature delivery")

    assert request is not None
    assert request.action == "start_planning"
    assert request.feature_request == "add a planning phase for feature delivery"


def test_user_prompt_hook_parses_bootstrap_request():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_workflow_request("/workflow bootstrap build a new greenfield workflow kernel")

    assert request is not None
    assert request.action == "start_bootstrap"
    assert request.feature_request == "build a new greenfield workflow kernel"


def test_user_prompt_hook_parses_revise_request():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_workflow_request("/workflow revise simplify the step breakdown")

    assert request is not None
    assert request.action == "revise_planning"
    assert request.feedback == "simplify the step breakdown"


def test_workflow_router_start_planning_creates_artifacts():
    workflow_router = _load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"

        response = workflow_router.start_planning(
            "Plan the workflow skill migration",
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

        state = json.loads(planning_state_path.read_text(encoding="utf-8"))
        metrics_dir = Path(tmpdir) / "metrics"
        scorecard = json.loads((metrics_dir / "scorecard.json").read_text(encoding="utf-8"))
        context_exists = Path(state["context_path"]).exists()
        scope_exists = Path(state["scope_contract_path"]).exists()
        architecture_exists = Path(state["architecture_constraints_path"]).exists()
        project_memory_exists = Path(state["project_memory_path"]).exists()
        requirements_memory_exists = Path(state["requirements_memory_path"]).exists()
        state_memory_exists = Path(state["state_memory_path"]).exists()
        metrics_events_exist = (metrics_dir / "events.jsonl").exists()
        metrics_scorecard_exist = (metrics_dir / "scorecard.json").exists()

    assert response.status == "ok"
    assert response.mode == "planning"
    assert state["status"] == "discuss"
    assert state["planning_mode"] == "brownfield"
    assert context_exists is True
    assert scope_exists is True
    assert architecture_exists is True
    assert project_memory_exists is True
    assert requirements_memory_exists is True
    assert state_memory_exists is True
    assert metrics_events_exist is True
    assert metrics_scorecard_exist is True
    assert scorecard["counts"]["planning_started"] == 1


def test_workflow_router_bootstrap_start_creates_greenfield_artifacts():
    workflow_router = _load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"

        response = workflow_router.start_planning(
            "Bootstrap a new workflow-first project",
            planning_mode="greenfield",
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

        state = json.loads(planning_state_path.read_text(encoding="utf-8"))
        stack_runtime_exists = Path(state["stack_runtime_decision_path"]).exists()
        bootstrap_expectations_exists = Path(state["bootstrap_expectations_path"]).exists()

    assert response.status == "ok"
    assert "bootstrap" in response.message
    assert state["planning_mode"] == "greenfield"
    assert stack_runtime_exists is True
    assert bootstrap_expectations_exists is True


def test_workflow_router_revise_planning_emits_metrics_event():
    workflow_router = _load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        workflow_router.start_planning(
            "Plan a workflow revision flow",
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

        response = workflow_router.revise_planning(
            "Tighten the scope and bootstrap notes.",
            planning_state_path=planning_state_path,
        )
        scorecard = json.loads(((Path(tmpdir) / "metrics") / "scorecard.json").read_text(encoding="utf-8"))

    assert response.status == "ok"
    assert scorecard["counts"]["planning_revised"] == 1


def test_workflow_router_execution_start_blocks_while_planning_is_active():
    workflow_router = _load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(_example_plan()), encoding="utf-8")

        workflow_router.start_planning(
            "Plan the guarded execution activation",
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )
        response = workflow_router.activate_execution(
            plan_path,
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )
        execution_state_exists = execution_state_path.exists()

    assert response.status == "blocked"
    assert execution_state_exists is False
    assert "planning-approve" in response.message
    assert "resume" in response.message
    assert "cancel" in response.message


def test_workflow_router_execution_start_blocks_while_execution_is_active():
    workflow_lib = _load_workflow_lib()
    workflow_router = _load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(_example_plan()), encoding="utf-8")

        active_state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        workflow_lib.save_state(active_state, execution_state_path)

        response = workflow_router.activate_execution(
            plan_path,
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )
        persisted_state = workflow_lib.load_state(execution_state_path)

    assert response.status == "blocked"
    assert persisted_state["workflow_name"] == active_state["workflow_name"]
    assert persisted_state["workflow_status"] == "active"
    assert "resume" in response.message
    assert "cancel" in response.message


def test_workflow_router_execution_start_allows_terminal_execution_replacement():
    workflow_lib = _load_workflow_lib()
    workflow_router = _load_workflow_router_lib()

    replacement_plan = _example_plan()
    replacement_plan["workflow_name"] = "Replacement workflow"

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(replacement_plan), encoding="utf-8")

        prior_state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="OLD.md"),
            tmpdir,
        )
        prior_state["workflow_name"] = "Old workflow"
        prior_state["workflow_status"] = "complete"
        prior_state["steps"][0]["status"] = "shipped"
        workflow_lib.save_state(prior_state, execution_state_path)

        response = workflow_router.activate_execution(
            plan_path,
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )
        persisted_state = workflow_lib.load_state(execution_state_path)

    assert response.status == "ok"
    assert persisted_state["workflow_name"] == "Replacement workflow"
    assert persisted_state["workflow_status"] == "active"


def test_workflow_router_approve_planning_blocks_while_execution_is_active():
    planning_lib = _load_planning_lib()
    workflow_lib = _load_workflow_lib()
    workflow_router = _load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"

        planning_state = _rebase_planning_state_paths(
            planning_lib.build_planning_state("Approve a guarded planning session"),
            tmpdir,
        )
        planning_state = planning_lib.set_planning_status(planning_state, "approval_ready")
        planning_lib.save_planning_state(planning_state, planning_state_path)

        active_state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        workflow_lib.save_state(active_state, execution_state_path)

        response = workflow_router.approve_current_plan(
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )
        persisted_state = workflow_lib.load_state(execution_state_path)
        planning_state_exists = planning_state_path.exists()

    assert response.status == "blocked"
    assert planning_state_exists is True
    assert persisted_state["workflow_name"] == active_state["workflow_name"]
    assert "resume" in response.message
    assert "cancel" in response.message


def test_workflow_skill_router_wrapper_blocks_execution_activation_while_planning_exists():
    plan = _example_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        planning_result = subprocess.run(
            [sys.executable, str(WORKFLOW_ROUTER_SKILL_SCRIPT_PATH), "--json", "planning-start", "Plan wrapper guardrails"],
            cwd=tmpdir,
            check=False,
            capture_output=True,
            text=True,
        )
        assert planning_result.returncode == 0, planning_result.stderr

        result = subprocess.run(
            [sys.executable, str(WORKFLOW_ROUTER_SKILL_SCRIPT_PATH), "--json", "execution-start", str(plan_path)],
            cwd=tmpdir,
            check=False,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "planning-approve" in payload["message"]


def test_user_prompt_hook_blocks_execution_activation_while_planning_exists():
    workflow_router = _load_workflow_router_lib()
    user_prompt_hook = _load_user_prompt_hook()
    plan = _example_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow_root = Path(tmpdir) / ".codex" / "workflow"
        planning_state_path = workflow_root / "planning_state.json"
        execution_state_path = workflow_root / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        workflow_router.start_planning(
            "Plan a legacy hook guard",
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

        request = user_prompt_hook.parse_workflow_request(f"/workflow start {plan_path}")
        assert request is not None

        original_planning_state_path = user_prompt_hook.DEFAULT_PLANNING_STATE_PATH
        original_execution_state_path = user_prompt_hook.DEFAULT_STATE_PATH
        stdout = io.StringIO()
        try:
            user_prompt_hook.DEFAULT_PLANNING_STATE_PATH = planning_state_path
            user_prompt_hook.DEFAULT_STATE_PATH = execution_state_path
            with contextlib.redirect_stdout(stdout):
                result_code = user_prompt_hook._handle_execution_activation(request)
        finally:
            user_prompt_hook.DEFAULT_PLANNING_STATE_PATH = original_planning_state_path
            user_prompt_hook.DEFAULT_STATE_PATH = original_execution_state_path

    assert result_code == 0
    payload = json.loads(stdout.getvalue())
    assert "blocked" in payload["systemMessage"]
    assert "planning-approve" in payload["hookSpecificOutput"]["additionalContext"]


def test_approve_planning_uses_planning_metrics_root_when_execution_path_differs():
    planning_lib = _load_planning_lib()
    workflow_router = _load_workflow_router_lib()

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
        _write_supporting_planning_artifacts(
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
        planning_scorecard = json.loads(((planning_root / "metrics") / "scorecard.json").read_text(encoding="utf-8"))

    assert execution_state["metrics_dir"] == str(planning_root / "metrics")
    assert planning_scorecard["counts"]["planning_started"] == 1
    assert planning_scorecard["counts"]["planning_approved"] == 1
    assert planning_scorecard["counts"]["execution_activated"] == 1
    assert (execution_root / "metrics" / "scorecard.json").exists() is False


def test_workflow_router_resume_advances_execution_state():
    workflow_lib = _load_workflow_lib()
    workflow_router = _load_workflow_router_lib()
    state = workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md")
    state["steps"][0]["status"] = "pending"

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        workflow_lib.save_state(state, execution_state_path)

        response = workflow_router.resume_workflow(
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )
        persisted_state = json.loads(execution_state_path.read_text(encoding="utf-8"))

    assert response.status == "ok"
    assert response.mode == "execution"
    assert "Start the next execution step." in response.additional_context
    assert persisted_state["steps"][0]["status"] == "implementing"


def test_workflow_router_resume_handles_gap_closure_and_replan_required():
    workflow_lib = _load_workflow_lib()
    workflow_router = _load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        execution_state_path = Path(tmpdir) / "state.json"
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["workflow_status"] = "gap_closure_pending"
        state["steps"][0]["status"] = "implementing"
        workflow_lib.save_state(state, execution_state_path)
        workflow_lib.save_uat_artifact(
            workflow_lib.build_uat_artifact(
                _example_plan(),
                workflow_name=state["workflow_name"],
                plan_path=state["plan_path"],
                project_memory_path="PROJECT.md",
                requirements_memory_path="REQUIREMENTS.md",
                state_memory_path="STATE.md",
            ),
            Path(state["uat_artifact_path"]),
        )
        workflow_lib.update_uat_artifact_result(
            Path(state["uat_artifact_path"]),
            "failed_gap",
            "One fixable verification gap remains.",
        )

        gap_response = workflow_router.resume_workflow(
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

        state["workflow_status"] = "replan_required"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, execution_state_path)
        workflow_lib.update_uat_artifact_result(
            Path(state["uat_artifact_path"]),
            "failed_replan",
            "The approved scope no longer matches the required architecture.",
        )

        replan_response = workflow_router.resume_workflow(
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

    assert "fixable gap" in gap_response.additional_context
    assert "follow-up planning session" in replan_response.additional_context


def test_workflow_router_allows_new_planning_after_replan_required():
    workflow_lib = _load_workflow_lib()
    workflow_router = _load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        execution_state_path = Path(tmpdir) / "state.json"
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["workflow_status"] = "replan_required"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, execution_state_path)

        response = workflow_router.start_planning(
            "Replan after UAT exposed an architecture mismatch",
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )
        planning_state_exists = planning_state_path.exists()

    assert response.status == "ok"
    assert planning_state_exists is True


def test_workflow_router_status_blocks_on_invalid_planning_state():
    workflow_router = _load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        planning_state_path.write_text(json.dumps({"status": "discuss"}), encoding="utf-8")

        response = workflow_router.status_summary(
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

    assert response.status == "blocked"
    assert "invalid" in response.message


def test_cancel_workflow_emits_metrics_event():
    workflow_router = _load_workflow_router_lib()

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
        scorecard = json.loads(((Path(tmpdir) / "metrics") / "scorecard.json").read_text(encoding="utf-8"))

    assert response.status == "ok"
    assert scorecard["counts"]["workflow_canceled"] == 1


def test_workflow_state_set_uat_status_passed_updates_state_and_artifact():
    workflow_lib = _load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        workflow_lib.save_uat_artifact(
            workflow_lib.build_uat_artifact(
                _example_plan(),
                workflow_name=state["workflow_name"],
                plan_path=state["plan_path"],
                project_memory_path="PROJECT.md",
                requirements_memory_path="REQUIREMENTS.md",
                state_memory_path="STATE.md",
            ),
            Path(state["uat_artifact_path"]),
        )

        result = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-uat-status",
                "passed",
                "--summary",
                "UAT passed cleanly.",
                "--path",
                str(state_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        persisted_state = workflow_lib.load_state(state_path)
        uat_artifact = workflow_lib.load_uat_artifact(Path(state["uat_artifact_path"]))

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "ship_pending"
    assert uat_artifact["overall_status"] == "passed"
    assert uat_artifact["summary"] == "UAT passed cleanly."


def test_workflow_state_set_uat_status_failed_gap_transitions_to_gap_closure():
    workflow_lib = _load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        workflow_lib.save_uat_artifact(
            workflow_lib.build_uat_artifact(
                _example_plan(),
                workflow_name=state["workflow_name"],
                plan_path=state["plan_path"],
                project_memory_path="PROJECT.md",
                requirements_memory_path="REQUIREMENTS.md",
                state_memory_path="STATE.md",
            ),
            Path(state["uat_artifact_path"]),
        )

        result = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-uat-status",
                "failed-gap",
                "--summary",
                "One fixable verification gap remains.",
                "--path",
                str(state_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        persisted_state = workflow_lib.load_state(state_path)
        uat_artifact = workflow_lib.load_uat_artifact(Path(state["uat_artifact_path"]))

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "gap_closure_pending"
    assert persisted_state["steps"][0]["status"] == "implementing"
    assert uat_artifact["overall_status"] == "failed_gap"


def test_workflow_state_set_uat_status_failed_replan_transitions_to_replan_required():
    workflow_lib = _load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["workflow_status"] = "uat_pending"
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)
        workflow_lib.save_uat_artifact(
            workflow_lib.build_uat_artifact(
                _example_plan(),
                workflow_name=state["workflow_name"],
                plan_path=state["plan_path"],
                project_memory_path="PROJECT.md",
                requirements_memory_path="REQUIREMENTS.md",
                state_memory_path="STATE.md",
            ),
            Path(state["uat_artifact_path"]),
        )

        result = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-uat-status",
                "failed-replan",
                "--summary",
                "The approved architecture no longer matches the needed scope.",
                "--path",
                str(state_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        persisted_state = workflow_lib.load_state(state_path)
        uat_artifact = workflow_lib.load_uat_artifact(Path(state["uat_artifact_path"]))

    assert result.returncode == 0, result.stderr
    assert persisted_state["workflow_status"] == "replan_required"
    assert uat_artifact["overall_status"] == "failed_replan"


def test_workflow_state_set_workflow_status_requires_override_reason_for_manual_change():
    workflow_lib = _load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["steps"][0]["status"] = "implementing"
        workflow_lib.save_state(state, state_path)

        missing_reason = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-workflow-status",
                "uat_pending",
                "--path",
                str(state_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        state_after_failure = workflow_lib.load_state(state_path)

        override_result = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-workflow-status",
                "uat_pending",
                "--override-reason",
                "manual reconciliation for regression coverage",
                "--path",
                str(state_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        persisted_state = workflow_lib.load_state(state_path)
        events_path = Path(state["metrics_dir"]) / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]

    assert missing_reason.returncode != 0
    assert "manual override" in missing_reason.stderr
    assert state_after_failure["workflow_status"] == "active"
    assert override_result.returncode == 0, override_result.stderr
    assert persisted_state["workflow_status"] == "uat_pending"
    assert [event["event"] for event in events] == ["override_used"]


def test_workflow_state_set_workflow_status_complete_requires_ship_pending_and_shipped():
    workflow_lib = _load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["steps"][0]["status"] = "committed"
        workflow_lib.save_state(state, state_path)

        wrong_status = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-workflow-status",
                "complete",
                "--path",
                str(state_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        state["workflow_status"] = "ship_pending"
        workflow_lib.save_state(state, state_path)

        not_shipped = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-workflow-status",
                "complete",
                "--path",
                str(state_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        persisted_state = workflow_lib.load_state(state_path)
        metrics_exists = (Path(state["metrics_dir"]) / "events.jsonl").exists()

    assert wrong_status.returncode != 0
    assert "ship_pending" in wrong_status.stderr
    assert not_shipped.returncode != 0
    assert "current step to be shipped" in not_shipped.stderr
    assert persisted_state["workflow_status"] == "ship_pending"
    assert metrics_exists is False


def test_workflow_state_set_step_status_shipped_requires_ship_pending_and_committed():
    workflow_lib = _load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        workflow_lib.save_state(state, state_path)

        wrong_status = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-step-status",
                "step-1",
                "shipped",
                "--path",
                str(state_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        state["workflow_status"] = "ship_pending"
        workflow_lib.save_state(state, state_path)
        not_committed = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-step-status",
                "step-1",
                "shipped",
                "--path",
                str(state_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        persisted_state = workflow_lib.load_state(state_path)

    assert wrong_status.returncode != 0
    assert "workflow_status ship_pending" in wrong_status.stderr
    assert not_committed.returncode != 0
    assert "current step to be committed" in not_committed.stderr
    assert persisted_state["steps"][0]["status"] == "implementing"


def test_next_stop_decision_requires_explicit_completion_after_shipped_step():
    workflow_lib = _load_workflow_lib()
    state = workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md")
    state["workflow_status"] = "ship_pending"
    state["steps"][0]["status"] = "shipped"

    next_state, decision, changed = workflow_lib.next_stop_decision(state)

    assert changed is False
    assert next_state["workflow_status"] == "ship_pending"
    assert decision.action == "block"
    assert "set-workflow-status complete" in (decision.prompt or "")


def test_metrics_scorecard_aggregates_representative_event_sequence():
    metrics_lib = _load_metrics_lib()

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


def test_metrics_scorecard_drops_canceled_session_from_timing_queue():
    metrics_lib = _load_metrics_lib()

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
    metrics_lib = _load_metrics_lib()

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
    workflow_lib = _load_workflow_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        state = _rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(_example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["steps"][0]["status"] = "implementing"
        workflow_lib.save_state(state, state_path)
        workflow_lib.save_uat_artifact(
            workflow_lib.build_uat_artifact(
                _example_plan(),
                workflow_name=state["workflow_name"],
                plan_path=state["plan_path"],
                project_memory_path="PROJECT.md",
                requirements_memory_path="REQUIREMENTS.md",
                state_memory_path="STATE.md",
            ),
            Path(state["uat_artifact_path"]),
        )

        commands = [
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-step-status",
                "step-1",
                "fix_pending",
                "--review-summary",
                "Missing regression assertion.",
                "--path",
                str(state_path),
            ],
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-step-status",
                "step-1",
                "commit_pending",
                "--review-summary",
                "review passed",
                "--path",
                str(state_path),
            ],
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-step-status",
                "step-1",
                "committed",
                "--path",
                str(state_path),
            ],
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-current-step",
                "step-1",
                "--override-reason",
                "manual state reconciliation",
                "--path",
                str(state_path),
            ],
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-workflow-status",
                "uat_pending",
                "--override-reason",
                "manual workflow-status reconciliation",
                "--path",
                str(state_path),
            ],
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-uat-status",
                "passed",
                "--summary",
                "Final UAT passed.",
                "--path",
                str(state_path),
            ],
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-step-status",
                "step-1",
                "shipped",
                "--path",
                str(state_path),
            ],
            [
                sys.executable,
                str(WORKFLOW_STATE_CLI_PATH),
                "set-workflow-status",
                "complete",
                "--path",
                str(state_path),
            ],
        ]
        for command in commands:
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr

        events_path = Path(state["metrics_dir"]) / "events.jsonl"
        scorecard_path = Path(state["metrics_dir"]) / "scorecard.json"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
        scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))

    event_names = [event["event"] for event in events]
    assert "review_failed" in event_names
    assert "review_passed" in event_names
    assert "step_committed" in event_names
    assert "override_used" in event_names
    assert "uat_passed" in event_names
    assert "workflow_shipped" in event_names
    assert scorecard["counts"]["review_failed"] == 1
    assert scorecard["counts"]["uat_passed"] == 1
    assert scorecard["counts"]["workflow_shipped"] == 1


def test_workflow_skill_is_scaffolded():
    assert WORKFLOW_SKILL_PATH.exists()
    assert WORKFLOW_SKILL_OPENAI_PATH.exists()
    assert WORKFLOW_ROUTER_SKILL_SCRIPT_PATH.exists()
    assert PLANNING_STATE_SKILL_SCRIPT_PATH.exists()
    assert WORKFLOW_STATE_SKILL_SCRIPT_PATH.exists()
    assert SHIP_SKILL_PATH.exists()
    assert SHIP_WORKFLOW_STATE_SKILL_SCRIPT_PATH.exists()

    skill_text = WORKFLOW_SKILL_PATH.read_text(encoding="utf-8")
    metadata_text = WORKFLOW_SKILL_OPENAI_PATH.read_text(encoding="utf-8")

    assert "python3 .agents/skills/workflow/scripts/workflow_router.py planning-start" in skill_text
    assert "python3 .agents/skills/workflow/scripts/workflow_router.py bootstrap-start" in skill_text
    assert "python3 .agents/skills/workflow/scripts/workflow_state.py set-uat-status" in skill_text
    assert "Deployment begins only after UAT moves the workflow to `ship_pending`." in skill_text
    assert ".codex/workflow/scripts/workflow_router.py" not in skill_text
    assert "Use $workflow" in metadata_text


def test_ship_skill_uses_bundled_workflow_state_wrapper():
    skill_text = SHIP_SKILL_PATH.read_text(encoding="utf-8")

    assert "python3 .agents/skills/ship/scripts/workflow_state.py set-step-status" in skill_text
    assert "ship_pending" in skill_text
    assert "user explicitly asked to ship anyway" not in skill_text
    assert ".codex/workflow/scripts/workflow_state.py" not in skill_text


def test_readme_and_next_steps_reflect_new_surface():
    readme_text = README_PATH.read_text(encoding="utf-8")
    next_steps_text = NEXT_STEPS_PATH.read_text(encoding="utf-8")

    assert "bootstrap-start" in readme_text
    assert "set-uat-status" in readme_text
    assert "set-workflow-status <status> --override-reason" in readme_text
    assert ".codex/workflow/metrics/" in readme_text
    assert "Kernel hardening first is complete" in next_steps_text
    assert "Strengthen planning audits beyond direct-consumer coverage." in next_steps_text
    assert "Keep scope to PR shipping only." in next_steps_text
    assert "Production rollout orchestration." in next_steps_text
    assert "There is still no explicit UAT/gap-closure/replan state machine" not in next_steps_text


def test_workflow_skill_router_wrapper_runs_from_foreign_worktree():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, str(WORKFLOW_ROUTER_SKILL_SCRIPT_PATH), "--json", "status"],
            cwd=tmpdir,
            check=False,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["mode"] == "status"
    assert payload["message"] == "no active workflow state"


def test_workflow_skill_router_wrapper_emits_bundled_planning_tool_path():
    expected_command = f"python3 {PLANNING_STATE_SKILL_SCRIPT_PATH}"

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, str(WORKFLOW_ROUTER_SKILL_SCRIPT_PATH), "--json", "planning-start", "Plan a wrapper-safe flow"],
            cwd=tmpdir,
            check=False,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert expected_command in payload["additional_context"]


def test_workflow_skill_router_wrapper_emits_bundled_workflow_state_tool_path():
    expected_command = f"python3 {WORKFLOW_STATE_SKILL_SCRIPT_PATH}"
    plan = _example_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(WORKFLOW_ROUTER_SKILL_SCRIPT_PATH), "--json", "execution-start", str(plan_path)],
            cwd=tmpdir,
            check=False,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert expected_command in payload["additional_context"]


def test_planning_prompt_uses_repo_local_planning_state_cli_by_default():
    planning_lib = _load_planning_lib()
    state = planning_lib.build_planning_state("Plan a plugin-safe workflow wrapper")

    prompt = planning_lib.planning_activation_prompt(state)

    assert "python3 .codex/workflow/scripts/planning_state.py audit-plan" in prompt
    assert "python3 .codex/workflow/scripts/planning_state.py advance discovery" in prompt


def test_compare_plan_cli_defaults_work_in_standalone_repo():
    result = subprocess.run(
        [sys.executable, str(PLANNING_STATE_SKILL_SCRIPT_PATH), "compare-plan"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Plan comparison:" in result.stdout


def test_plugin_manifest_does_not_claim_hook_bundling():
    manifest = json.loads(PLUGIN_MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["skills"] == "./.agents/skills/"
    assert "hooks" not in manifest


def test_planning_artifacts_are_initialized():
    planning_lib = _load_planning_lib()
    state = planning_lib.build_planning_state("Add a planning workflow")

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state["approved_plan_path"] = str(Path(tmpdir) / "approved-plan.json")
        state["context_path"] = str(Path(tmpdir) / "context.json")
        state["discovery_dossier_path"] = str(Path(tmpdir) / "discovery_dossier.json")
        state["scope_contract_path"] = str(Path(tmpdir) / "scope_contract.json")
        state["architecture_constraints_path"] = str(Path(tmpdir) / "architecture_constraints.json")
        state["product_scope_audit_path"] = str(Path(tmpdir) / "product_scope_audit.json")
        state["skeptic_audit_path"] = str(Path(tmpdir) / "skeptic_audit.json")
        state["convergence_summary_path"] = str(Path(tmpdir) / "convergence_summary.json")
        state["planning_trace_path"] = str(Path(tmpdir) / "planning_trace.json")
        state["project_memory_path"] = str(Path(tmpdir) / "PROJECT.md")
        state["requirements_memory_path"] = str(Path(tmpdir) / "REQUIREMENTS.md")
        state["state_memory_path"] = str(Path(tmpdir) / "STATE.md")

        planning_lib.save_planning_state(state, planning_state_path)
        planning_lib.initialize_planning_artifacts(state)

        context = json.loads(Path(state["context_path"]).read_text(encoding="utf-8"))
        discovery = json.loads(Path(state["discovery_dossier_path"]).read_text(encoding="utf-8"))
        scope_contract = json.loads(Path(state["scope_contract_path"]).read_text(encoding="utf-8"))
        architecture_constraints = json.loads(
            Path(state["architecture_constraints_path"]).read_text(encoding="utf-8")
        )
        product_scope_audit = json.loads(
            Path(state["product_scope_audit_path"]).read_text(encoding="utf-8")
        )
        skeptic_audit = json.loads(Path(state["skeptic_audit_path"]).read_text(encoding="utf-8"))
        convergence_summary = json.loads(
            Path(state["convergence_summary_path"]).read_text(encoding="utf-8")
        )
        trace = json.loads(Path(state["planning_trace_path"]).read_text(encoding="utf-8"))
        project_memory = Path(state["project_memory_path"]).read_text(encoding="utf-8")
        requirements_memory = Path(state["requirements_memory_path"]).read_text(encoding="utf-8")
        state_memory = Path(state["state_memory_path"]).read_text(encoding="utf-8")

    assert context["feature_request"] == "Add a planning workflow"
    assert context["goal"] == ""
    assert discovery["feature_request"] == "Add a planning workflow"
    assert discovery["current"]["entry_points"] == []
    assert scope_contract["must_have"] == []
    assert architecture_constraints["required_reuse"] == []
    assert product_scope_audit["recommendation"] == "pending"
    assert skeptic_audit["recommendation"] == "pending"
    assert convergence_summary["approval_summary"] == ""
    assert trace["events"][0]["event"] == "planning_started"
    assert "## Product Intent" in project_memory
    assert "## Deferred Scope" in requirements_memory
    assert "## Active Initiative" in state_memory


def test_greenfield_architecture_audit_requires_stack_runtime_decision():
    planning_lib = _load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state(
            "Bootstrap a greenfield workflow kernel",
            planning_mode="greenfield",
        ),
        "architecture_audit",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_planning_state_paths(state, tmpdir)
        planning_lib.initialize_planning_artifacts(state)
        _write_supporting_planning_artifacts(state, active_initiative="Bootstrap the greenfield kernel.")
        Path(state["discovery_dossier_path"]).write_text(
            json.dumps(
                {
                    "version": 1,
                    "feature_request": state["feature_request"],
                    "current": {
                        "requirements": ["Bootstrap the kernel."],
                        "assumptions": ["Python is the preferred runtime."],
                        "anti_goals": [],
                        "success_criteria": ["A baseline implementation plan is possible."],
                        "entry_points": [],
                        "blast_radius": ["No existing blast radius; constrain initial scope."],
                        "pattern_anchors": [],
                        "verification_anchors": ["tests/scripts/test_codex_workflow.py"],
                        "open_questions": [],
                        "complexity_events": [],
                    },
                    "supplements": [],
                }
            ),
            encoding="utf-8",
        )

        issues = planning_lib.validate_phase_outputs(state, phase="architecture_audit")
        _write_greenfield_planning_artifacts(state)
        repaired_issues = planning_lib.validate_phase_outputs(state, phase="architecture_audit")

    assert any("runtime_language_choice" in issue for issue in issues)
    assert repaired_issues == []


def test_greenfield_convergence_requires_bootstrap_expectations():
    planning_lib = _load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state(
            "Bootstrap a greenfield workflow kernel",
            planning_mode="greenfield",
        ),
        "convergence",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_planning_state_paths(state, tmpdir)
        planning_lib.initialize_planning_artifacts(state)
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=[
                "Embedding service public behavior",
            ],
            active_initiative="Bootstrap the greenfield kernel.",
        )
        Path(state["approved_plan_path"]).write_text(json.dumps(_example_plan()), encoding="utf-8")
        Path(state["discovery_dossier_path"]).write_text(
            json.dumps(
                {
                    "version": 1,
                    "feature_request": state["feature_request"],
                    "current": {
                        "requirements": ["Bootstrap the kernel."],
                        "assumptions": ["Python is the preferred runtime."],
                        "anti_goals": [],
                        "success_criteria": ["A baseline implementation plan is possible."],
                        "entry_points": [],
                        "blast_radius": ["No existing blast radius; constrain initial scope."],
                        "pattern_anchors": [],
                        "verification_anchors": ["tests/scripts/test_codex_workflow.py"],
                        "open_questions": [],
                        "complexity_events": [],
                    },
                    "supplements": [],
                }
            ),
            encoding="utf-8",
        )
        _write_greenfield_planning_artifacts(state)
        Path(state["bootstrap_expectations_path"]).write_text(
            json.dumps(
                {
                    "version": 1,
                    "feature_request": state["feature_request"],
                    "ci_testing_baseline_expectations": [],
                    "deployment_release_baseline_expectations": [],
                }
            ),
            encoding="utf-8",
        )

        issues = planning_lib.validate_phase_outputs(state, phase="convergence")
        _write_greenfield_planning_artifacts(state)
        repaired_issues = planning_lib.validate_phase_outputs(state, phase="convergence")

    assert any("ci_testing_baseline_expectations" in issue for issue in issues)
    assert repaired_issues == []


def test_approve_planning_ingests_execution_state():
    planning_lib = _load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state("Ship the example plan"),
        "approval_ready",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        approved_plan_path = Path(tmpdir) / "approved-plan.json"
        execution_state_path = Path(tmpdir) / "state.json"
        context_path = Path(tmpdir) / "context.json"
        discovery_dossier_path = Path(tmpdir) / "discovery_dossier.json"
        scope_contract_path = Path(tmpdir) / "scope_contract.json"
        architecture_constraints_path = Path(tmpdir) / "architecture_constraints.json"
        product_scope_audit_path = Path(tmpdir) / "product_scope_audit.json"
        skeptic_audit_path = Path(tmpdir) / "skeptic_audit.json"
        convergence_summary_path = Path(tmpdir) / "convergence_summary.json"
        planning_trace_path = Path(tmpdir) / "planning_trace.json"
        project_memory_path = Path(tmpdir) / "PROJECT.md"
        requirements_memory_path = Path(tmpdir) / "REQUIREMENTS.md"
        state_memory_path = Path(tmpdir) / "STATE.md"

        approved_plan_path.write_text(PLAN_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        state["approved_plan_path"] = str(approved_plan_path)
        state["context_path"] = str(context_path)
        state["discovery_dossier_path"] = str(discovery_dossier_path)
        state["scope_contract_path"] = str(scope_contract_path)
        state["architecture_constraints_path"] = str(architecture_constraints_path)
        state["product_scope_audit_path"] = str(product_scope_audit_path)
        state["skeptic_audit_path"] = str(skeptic_audit_path)
        state["convergence_summary_path"] = str(convergence_summary_path)
        state["planning_trace_path"] = str(planning_trace_path)
        state["project_memory_path"] = str(project_memory_path)
        state["requirements_memory_path"] = str(requirements_memory_path)
        state["state_memory_path"] = str(state_memory_path)

        planning_lib.save_planning_state(state, planning_state_path)
        planning_lib.initialize_planning_artifacts(state)
        _write_supporting_planning_artifacts(
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

        persisted_state = json.loads(execution_state_path.read_text(encoding="utf-8"))
        uat_artifact = json.loads(Path(execution_state["uat_artifact_path"]).read_text(encoding="utf-8"))
        scorecard = json.loads((Path(execution_state["metrics_dir"]) / "scorecard.json").read_text(encoding="utf-8"))

    assert execution_state["workflow_name"] == "Example feature rollout"
    assert persisted_state["current_step_id"] == "step-1"
    assert planning_state_path.exists() is False
    assert uat_artifact["overall_status"] == "pending"
    assert any(item["id"] == "repo-memory-consistency" for item in uat_artifact["checklist"])
    assert scorecard["counts"]["planning_approved"] == 1
    assert scorecard["counts"]["execution_activated"] == 1


def test_planning_audit_requires_direct_consumer_tests_for_compatibility_steps():
    planning_lib = _load_planning_lib()
    state = planning_lib.build_planning_state("Preserve compatibility for enrichment consumers")

    approved_plan = {
        "workflow_name": "Compatibility coverage",
        "summary": "Keep the existing enrichment consumers compatible during a refactor.",
        "requirements": [
            {
                "id": "R1",
                "kind": "verification",
                "text": "Verify API, batch, and filter compatibility through direct consumer tests.",
            }
        ],
        "assumptions": [],
        "open_questions": [],
        "out_of_scope": [],
        "steps": [
            {
                "id": "step-1",
                "title": "Prove compatibility for API, batch, and filter consumers",
                "goal": "Validate that the refactor preserves the current consumer interface.",
                "requirement_ids": ["R1"],
                "context": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "planned_updates": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "planned_creates": [],
                "constraints": ["Keep this step compatibility-focused."],
                "justification": "This step proves that the refactor does not break direct consumers.",
                "files_read_first": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "interfaces_to_preserve": ["Current enrichment consumer interface"],
                "avoid_touching": ["app/orchestrators/single_enrichment.py"],
                "verification_targets": ["tests/e2e/test_enrichment_flow.py"],
                "risk_flags": ["Preserve the current enrichment consumer interface."],
                "blast_radius": [
                    "app/api/ai_enrichment.py consumers",
                    "app/orchestrators/batch_enrichment.py consumers",
                    "app/orchestrators/filter_batch.py consumers",
                ],
                "decision_ids": ["D-COMPAT-1"],
                "depends_on": [],
                "wave": 1,
                "file_ownership": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "rollback_notes": ["Revert the compatibility step if any consumer contract regresses."],
                "operational_watchpoints": [
                    "Watch direct enrichment consumer tests while the refactor lands."
                ],
                "done_when": ["Existing consumers remain compatible."],
                "verify_cmds": ["uv run pytest tests/e2e/test_enrichment_flow.py"],
                "commit_message": "refactor: preserve consumer compatibility",
            }
        ],
    }
    discovery_dossier = {
        "version": 1,
        "feature_request": state["feature_request"],
        "current": {
            "requirements": [],
            "anti_goals": [],
            "success_criteria": [],
            "entry_points": [
                "app/api/ai_enrichment.py",
                "app/orchestrators/batch_enrichment.py",
                "app/orchestrators/filter_batch.py",
            ],
            "blast_radius": [
                "AI enrichment API route instantiates SingleEnrichmentOrchestrator directly.",
                "BatchEnrichmentOrchestrator reuses SingleEnrichmentOrchestrator per item.",
                "FilterBatchOrchestrator reuses SingleEnrichmentOrchestrator per item.",
            ],
            "pattern_anchors": [],
            "verification_anchors": [],
            "open_questions": [],
            "complexity_events": [],
        },
        "supplements": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        approved_plan_path = Path(tmpdir) / "approved-plan.json"
        context_path = Path(tmpdir) / "context.json"
        discovery_dossier_path = Path(tmpdir) / "discovery_dossier.json"
        scope_contract_path = Path(tmpdir) / "scope_contract.json"
        architecture_constraints_path = Path(tmpdir) / "architecture_constraints.json"
        product_scope_audit_path = Path(tmpdir) / "product_scope_audit.json"
        skeptic_audit_path = Path(tmpdir) / "skeptic_audit.json"
        convergence_summary_path = Path(tmpdir) / "convergence_summary.json"
        planning_trace_path = Path(tmpdir) / "planning_trace.json"
        project_memory_path = Path(tmpdir) / "PROJECT.md"
        requirements_memory_path = Path(tmpdir) / "REQUIREMENTS.md"
        state_memory_path = Path(tmpdir) / "STATE.md"

        approved_plan_path.write_text(json.dumps(approved_plan), encoding="utf-8")
        discovery_dossier_path.write_text(json.dumps(discovery_dossier), encoding="utf-8")
        state["approved_plan_path"] = str(approved_plan_path)
        state["context_path"] = str(context_path)
        state["discovery_dossier_path"] = str(discovery_dossier_path)
        state["scope_contract_path"] = str(scope_contract_path)
        state["architecture_constraints_path"] = str(architecture_constraints_path)
        state["product_scope_audit_path"] = str(product_scope_audit_path)
        state["skeptic_audit_path"] = str(skeptic_audit_path)
        state["convergence_summary_path"] = str(convergence_summary_path)
        state["planning_trace_path"] = str(planning_trace_path)
        state["project_memory_path"] = str(project_memory_path)
        state["requirements_memory_path"] = str(requirements_memory_path)
        state["state_memory_path"] = str(state_memory_path)
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Current enrichment consumer interface"],
            active_initiative="Keep the existing enrichment consumers compatible during a refactor.",
        )

        issues = planning_lib.audit_planning_artifacts(state)

    assert any("tests/api/test_ai_enrichment.py" in issue for issue in issues)
    assert any("tests/orchestrators/test_batch_enrichment.py" in issue for issue in issues)
    assert any("tests/orchestrators/test_filter_batch.py" in issue for issue in issues)


def test_approve_planning_rejects_underverified_compatibility_plan():
    planning_lib = _load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state("Preserve compatibility for enrichment consumers"),
        "approval_ready",
    )

    approved_plan = {
        "workflow_name": "Compatibility coverage",
        "summary": "Keep the existing enrichment consumers compatible during a refactor.",
        "requirements": [
            {
                "id": "R1",
                "kind": "verification",
                "text": "Verify API, batch, and filter compatibility through direct consumer tests.",
            }
        ],
        "assumptions": [],
        "open_questions": [],
        "out_of_scope": [],
        "steps": [
            {
                "id": "step-1",
                "title": "Prove compatibility for API, batch, and filter consumers",
                "goal": "Validate that the refactor preserves the current consumer interface.",
                "requirement_ids": ["R1"],
                "context": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "planned_updates": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "planned_creates": [],
                "constraints": ["Keep this step compatibility-focused."],
                "justification": "This step proves that the refactor does not break direct consumers.",
                "files_read_first": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "interfaces_to_preserve": ["Current enrichment consumer interface"],
                "avoid_touching": ["app/orchestrators/single_enrichment.py"],
                "verification_targets": ["tests/e2e/test_enrichment_flow.py"],
                "risk_flags": ["Preserve the current enrichment consumer interface."],
                "blast_radius": [
                    "app/api/ai_enrichment.py consumers",
                    "app/orchestrators/batch_enrichment.py consumers",
                    "app/orchestrators/filter_batch.py consumers",
                ],
                "decision_ids": ["D-COMPAT-1"],
                "depends_on": [],
                "wave": 1,
                "file_ownership": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "rollback_notes": ["Revert the compatibility step if any consumer contract regresses."],
                "operational_watchpoints": [
                    "Watch direct enrichment consumer tests while the refactor lands."
                ],
                "done_when": ["Existing consumers remain compatible."],
                "verify_cmds": ["uv run pytest tests/e2e/test_enrichment_flow.py"],
                "commit_message": "refactor: preserve consumer compatibility",
            }
        ],
    }
    discovery_dossier = {
        "version": 1,
        "feature_request": state["feature_request"],
        "current": {
            "requirements": [],
            "anti_goals": [],
            "success_criteria": [],
            "entry_points": [
                "app/api/ai_enrichment.py",
                "app/orchestrators/batch_enrichment.py",
                "app/orchestrators/filter_batch.py",
            ],
            "blast_radius": [],
            "pattern_anchors": [],
            "verification_anchors": [],
            "open_questions": [],
            "complexity_events": [],
        },
        "supplements": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        approved_plan_path = Path(tmpdir) / "approved-plan.json"
        context_path = Path(tmpdir) / "context.json"
        discovery_dossier_path = Path(tmpdir) / "discovery_dossier.json"
        scope_contract_path = Path(tmpdir) / "scope_contract.json"
        architecture_constraints_path = Path(tmpdir) / "architecture_constraints.json"
        product_scope_audit_path = Path(tmpdir) / "product_scope_audit.json"
        skeptic_audit_path = Path(tmpdir) / "skeptic_audit.json"
        convergence_summary_path = Path(tmpdir) / "convergence_summary.json"
        planning_trace_path = Path(tmpdir) / "planning_trace.json"
        project_memory_path = Path(tmpdir) / "PROJECT.md"
        requirements_memory_path = Path(tmpdir) / "REQUIREMENTS.md"
        state_memory_path = Path(tmpdir) / "STATE.md"

        approved_plan_path.write_text(json.dumps(approved_plan), encoding="utf-8")
        discovery_dossier_path.write_text(json.dumps(discovery_dossier), encoding="utf-8")
        state["approved_plan_path"] = str(approved_plan_path)
        state["context_path"] = str(context_path)
        state["discovery_dossier_path"] = str(discovery_dossier_path)
        state["scope_contract_path"] = str(scope_contract_path)
        state["architecture_constraints_path"] = str(architecture_constraints_path)
        state["product_scope_audit_path"] = str(product_scope_audit_path)
        state["skeptic_audit_path"] = str(skeptic_audit_path)
        state["convergence_summary_path"] = str(convergence_summary_path)
        state["planning_trace_path"] = str(planning_trace_path)
        state["project_memory_path"] = str(project_memory_path)
        state["requirements_memory_path"] = str(requirements_memory_path)
        state["state_memory_path"] = str(state_memory_path)

        planning_lib.save_planning_state(state, planning_state_path)
        planning_lib.initialize_planning_artifacts(state)
        discovery_dossier_path.write_text(json.dumps(discovery_dossier), encoding="utf-8")
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Current enrichment consumer interface"],
            active_initiative="Keep the existing enrichment consumers compatible during a refactor.",
        )

        try:
            planning_lib.approve_planning(
                state,
                planning_state_path=planning_state_path,
                execution_state_path=execution_state_path,
            )
        except ValueError as exc:
            assert "failed planning audit" in str(exc)
            assert "tests/api/test_ai_enrichment.py" in str(exc)
        else:
            raise AssertionError("expected approve_planning to reject under-verified compatibility plan")


def test_convergence_cannot_advance_to_approval_ready_while_audit_is_dirty():
    planning_lib = _load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state("Guard the final approval gate"),
        "convergence",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_planning_state_paths(state, tmpdir)
        approved_plan_path = Path(state["approved_plan_path"])
        approved_plan_path.write_text(json.dumps(_example_plan()), encoding="utf-8")
        planning_lib.initialize_planning_artifacts(state)
        Path(state["discovery_dossier_path"]).write_text(
            json.dumps(
                {
                    "version": 1,
                    "feature_request": state["feature_request"],
                    "current": {
                        "requirements": ["Update the embedding behavior."],
                        "anti_goals": [],
                        "success_criteria": ["The embedding flow uses the updated behavior."],
                        "entry_points": ["app/ai/embedding/service.py"],
                        "blast_radius": ["Embedding service consumers depend on the current output shape."],
                        "pattern_anchors": [],
                        "verification_anchors": ["tests/ai/test_embedding_service.py"],
                        "open_questions": [],
                        "complexity_events": [],
                    },
                    "supplements": [],
                }
            ),
            encoding="utf-8",
        )
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Embedding service public behavior"],
            active_initiative="A different initiative that should fail the memory audit.",
        )

        try:
            planning_lib.advance_planning_phase(state, target_status="approval_ready")
        except ValueError as exc:
            assert "STATE.md" in str(exc)
        else:
            raise AssertionError("expected approval_ready advancement to enforce the final audit gate")


def test_repo_memory_drift_detection_flags_deferred_scope_leaks():
    planning_lib = _load_planning_lib()
    state = planning_lib.build_planning_state("Protect repo memory from drift")

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_planning_state_paths(state, tmpdir)
        approved_plan_path = Path(state["approved_plan_path"])
        approved_plan_path.write_text(json.dumps(_example_plan()), encoding="utf-8")
        Path(state["discovery_dossier_path"]).write_text(
            json.dumps(
                {
                    "version": 1,
                    "feature_request": state["feature_request"],
                    "current": {
                        "requirements": ["Update the embedding behavior."],
                        "anti_goals": [],
                        "success_criteria": ["The embedding flow uses the updated behavior."],
                        "entry_points": ["app/ai/embedding/service.py"],
                        "blast_radius": ["Embedding service consumers depend on the current output shape."],
                        "pattern_anchors": [],
                        "verification_anchors": ["tests/ai/test_embedding_service.py"],
                        "open_questions": [],
                        "complexity_events": [],
                    },
                    "supplements": [],
                }
            ),
            encoding="utf-8",
        )
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Embedding service public behavior"],
            deferred=["embedding behavior"],
            active_initiative="Update the embedding flow in one verified step.",
        )

        issues = planning_lib.audit_planning_artifacts(state)

    assert any("REQUIREMENTS.md" in issue for issue in issues)
    assert any("embedding behavior" in issue for issue in issues)


def test_compare_plan_specs_reports_stronger_candidate():
    planning_lib = _load_planning_lib()
    baseline = _example_plan()
    for field_name in (
        "justification",
        "files_read_first",
        "interfaces_to_preserve",
        "avoid_touching",
        "verification_targets",
        "wave",
        "file_ownership",
        "rollback_notes",
        "operational_watchpoints",
    ):
        baseline["steps"][0].pop(field_name, None)
    candidate = deepcopy(baseline)
    candidate["steps"][0]["justification"] = "Keep the first slice strictly focused on the embedding service."
    candidate["steps"][0]["files_read_first"] = ["app/ai/embedding/service.py"]
    candidate["steps"][0]["interfaces_to_preserve"] = ["Embedding service public behavior"]
    candidate["steps"][0]["avoid_touching"] = ["app/api/embedding.py"]
    candidate["steps"][0]["verification_targets"] = [
        "tests/ai/test_embedding_service.py",
        "tests/ai/test_embedding_contract.py",
    ]
    candidate["steps"][0]["wave"] = 1
    candidate["steps"][0]["file_ownership"] = [
        "app/ai/embedding/service.py",
        "tests/ai/test_embedding_service.py",
    ]
    candidate["steps"][0]["rollback_notes"] = [
        "Revert the embedding step if the consumer contract regresses.",
    ]
    candidate["steps"][0]["operational_watchpoints"] = [
        "Watch the embedding service contract during verification.",
    ]
    candidate["steps"][0]["done_when"].append("Targeted regression coverage proves the contract did not drift.")
    candidate["steps"][0]["verify_cmds"].append("uv run pytest tests/ai/test_embedding_contract.py")

    comparison = planning_lib.compare_plan_specs(baseline, candidate)

    assert comparison["verdict"] == "stronger"
    assert any("step justification coverage" in item for item in comparison["improved"])
    assert any("read-first handoff coverage" in item for item in comparison["improved"])
    assert any("completion detail per step" in item for item in comparison["improved"])
    assert any("verification target breadth" in item for item in comparison["improved"])
    assert any("file ownership coverage" in item for item in comparison["improved"])
    assert any("rollback note coverage" in item for item in comparison["improved"])


def test_render_plan_comparison_includes_verdict_and_metric_changes():
    planning_lib = _load_planning_lib()
    baseline = _example_plan()
    candidate = deepcopy(baseline)
    candidate["steps"][0]["justification"] = "Preserve the existing service interface."
    candidate["steps"][0]["done_when"].append("The embedding regression command passes.")

    comparison = planning_lib.compare_plan_specs(baseline, candidate)
    rendered = planning_lib.render_plan_comparison(
        comparison,
        baseline_label="baseline.json",
        candidate_label="candidate.json",
    )

    assert "Plan comparison: `baseline.json` -> `candidate.json`" in rendered
    assert "Verdict: stronger" in rendered
    assert "missing justifications" in rendered


def test_evaluate_plan_spec_flags_dependency_cycles_and_wave_errors():
    planning_lib = _load_planning_lib()
    plan = json.loads(PLAN_EXAMPLE_PATH.read_text(encoding="utf-8"))
    plan["steps"][0]["depends_on"] = ["step-2"]
    plan["steps"][0]["wave"] = 2
    plan["steps"][1]["depends_on"] = ["step-1"]
    plan["steps"][1]["wave"] = 2

    evaluation = planning_lib.evaluate_plan_spec(plan)

    assert any("dependency cycle detected" in item for item in evaluation["warnings"])
    assert any("must be greater than dependency" in item for item in evaluation["warnings"])


def test_evaluate_plan_spec_flags_parallel_file_ownership_conflicts():
    planning_lib = _load_planning_lib()
    plan = json.loads(PLAN_EXAMPLE_PATH.read_text(encoding="utf-8"))
    plan["steps"][1]["wave"] = 1
    plan["steps"][1]["file_ownership"] = [
        "app/example/module.py",
        "tests/example/test_second_module.py",
    ]

    evaluation = planning_lib.evaluate_plan_spec(plan)

    assert any("conflicting file ownership" in item for item in evaluation["warnings"])


def test_evaluate_plan_spec_flags_missing_rollback_and_watchpoints_for_risky_steps():
    planning_lib = _load_planning_lib()
    plan = _example_plan()
    plan["steps"][0].pop("rollback_notes")
    plan["steps"][0].pop("operational_watchpoints")

    evaluation = planning_lib.evaluate_plan_spec(plan)

    assert any("missing rollback_notes" in item for item in evaluation["warnings"])
    assert any("missing operational_watchpoints" in item for item in evaluation["warnings"])


def test_user_prompt_hook_ignores_normal_prompts():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_workflow_request("implement the approved plan")

    assert request is None
