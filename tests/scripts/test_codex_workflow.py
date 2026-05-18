from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / ".codex" / "workflow" / "scripts"
WORKFLOW_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "workflow_lib.py"
PLANNING_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "planning_lib.py"
WORKFLOW_ROUTER_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "workflow_router_lib.py"
PLANNING_STATE_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "planning_state.example.json"
PLAN_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "plan.example.json"


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


def _load_workflow_router_lib():
    return _load_module("codex_workflow_router_lib", WORKFLOW_ROUTER_LIB_PATH)


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
                "delivery_contract": {
                    "mode": "one_shot",
                    "comparison_required": False,
                    "basis": "user request, repo context, and bounded clarification",
                },
                "goal": "Ship a decision-complete plan.",
                "target_user": "Workflow maintainers",
                "desired_behavior": "The planner should produce a safe, implementable plan.",
                "good_outcomes": ["The implementer can follow the plan directly."],
                "bad_outcomes": ["The plan leaves architecture or verification decisions open."],
                "locked_decisions": ["Keep planning artifacts JSON-first."],
                "defaults_taken": ["Prefer the smallest viable slice."],
                "open_questions": open_questions or [],
                "clarification_gate": {
                    "material_questions": [],
                    "no_material_questions_reason": "The request is narrow enough to plan without changing product scope.",
                },
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
    assert context["delivery_contract"]["mode"] == "one_shot"
    assert context["delivery_contract"]["comparison_required"] is False
    assert context["goal"] == ""
    assert context["clarification_gate"]["material_questions"] == []
    assert discovery["feature_request"] == "Add a planning workflow"
    assert discovery["current"]["entry_points"] == []
    assert discovery["current"]["comparison_diagnostic"]["mode"] == "none"
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
            "direct_verification_matrix": [
                {
                    "entry_point": "app/api/ai_enrichment.py",
                    "verification_targets": ["tests/contracts/test_ai_enrichment_route.py"],
                },
                {
                    "entry_point": "app/orchestrators/batch_enrichment.py",
                    "verification_targets": ["tests/contracts/test_batch_enrichment_orchestrator.py"],
                },
                {
                    "entry_point": "app/orchestrators/filter_batch.py",
                    "verification_targets": ["tests/contracts/test_filter_batch_orchestrator.py"],
                },
            ],
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

    assert any("tests/contracts/test_ai_enrichment_route.py" in issue for issue in issues)
    assert any("tests/contracts/test_batch_enrichment_orchestrator.py" in issue for issue in issues)
    assert any("tests/contracts/test_filter_batch_orchestrator.py" in issue for issue in issues)


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
            "direct_verification_matrix": [
                {
                    "entry_point": "app/api/ai_enrichment.py",
                    "verification_targets": ["tests/contracts/test_ai_enrichment_route.py"],
                },
                {
                    "entry_point": "app/orchestrators/batch_enrichment.py",
                    "verification_targets": ["tests/contracts/test_batch_enrichment_orchestrator.py"],
                },
                {
                    "entry_point": "app/orchestrators/filter_batch.py",
                    "verification_targets": ["tests/contracts/test_filter_batch_orchestrator.py"],
                },
            ],
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
            assert "tests/contracts/test_ai_enrichment_route.py" in str(exc)
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
