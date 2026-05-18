from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


TESTS_SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / ".codex" / "workflow" / "scripts"


if str(TESTS_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_SCRIPTS_DIR))
if str(WORKFLOW_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS_DIR))


from workflow_test_support import (  # noqa: E402
    PLAN_EXAMPLE_PATH,
    PLANNING_STATE_EXAMPLE_PATH,
    example_plan,
    load_planning_lib,
    rebase_planning_state_paths,
    write_greenfield_planning_artifacts,
    write_supporting_planning_artifacts,
)


def test_example_planning_state_is_valid():
    planning_lib = load_planning_lib()
    state = json.loads(PLANNING_STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    planning_lib.validate_planning_state(state)


def test_build_planning_state_starts_in_discuss():
    planning_lib = load_planning_lib()

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
    planning_lib = load_planning_lib()

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


def test_load_planning_state_infers_checkpoint_for_legacy_revising_session():
    planning_lib = load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        state = rebase_planning_state_paths(
            planning_lib.build_planning_state("Revise an in-flight planning session"),
            tmpdir,
        )
        planning_lib.initialize_planning_artifacts(state)
        Path(state["approved_plan_path"]).write_text(json.dumps(example_plan()), encoding="utf-8")
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
    planning_lib = load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = rebase_planning_state_paths(
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
    planning_lib = load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = rebase_planning_state_paths(
            planning_lib.build_planning_state("Plan a gated workflow"),
            tmpdir,
        )
        planning_lib.initialize_planning_artifacts(state)
        write_supporting_planning_artifacts(
            state,
            active_initiative="Produce an approval-ready plan.",
        )

        advanced_state = planning_lib.advance_planning_phase(state, target_status="discovery")

    assert advanced_state["status"] == "discovery"
    assert advanced_state["phase_checkpoint"] == "discovery"


def test_blocked_planning_phase_stays_blocked_until_artifacts_are_repaired():
    planning_lib = load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = rebase_planning_state_paths(
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

        write_supporting_planning_artifacts(
            state,
            active_initiative="Produce an approval-ready plan.",
        )
        advanced_state = planning_lib.advance_planning_phase(state, target_status="discovery")

    assert advanced_state["status"] == "discovery"
    assert advanced_state["phase_checkpoint"] == "discovery"


def test_planning_artifacts_are_initialized():
    planning_lib = load_planning_lib()
    state = planning_lib.build_planning_state("Add a planning workflow")

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state = rebase_planning_state_paths(state, tmpdir)

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
    planning_lib = load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state(
            "Bootstrap a greenfield workflow kernel",
            planning_mode="greenfield",
        ),
        "architecture_audit",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        state = rebase_planning_state_paths(state, tmpdir)
        planning_lib.initialize_planning_artifacts(state)
        write_supporting_planning_artifacts(state, active_initiative="Bootstrap the greenfield kernel.")
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
                        "verification_anchors": ["tests/scripts/test_planning_lifecycle.py"],
                        "open_questions": [],
                        "complexity_events": [],
                    },
                    "supplements": [],
                }
            ),
            encoding="utf-8",
        )

        issues = planning_lib.validate_phase_outputs(state, phase="architecture_audit")
        write_greenfield_planning_artifacts(state)
        repaired_issues = planning_lib.validate_phase_outputs(state, phase="architecture_audit")

    assert any("runtime_language_choice" in issue for issue in issues)
    assert repaired_issues == []


def test_greenfield_convergence_requires_bootstrap_expectations():
    planning_lib = load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state(
            "Bootstrap a greenfield workflow kernel",
            planning_mode="greenfield",
        ),
        "convergence",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        state = rebase_planning_state_paths(state, tmpdir)
        planning_lib.initialize_planning_artifacts(state)
        write_supporting_planning_artifacts(
            state,
            preserved_interfaces=[
                "Embedding service public behavior",
            ],
            active_initiative="Bootstrap the greenfield kernel.",
        )
        Path(state["approved_plan_path"]).write_text(json.dumps(example_plan()), encoding="utf-8")
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
                        "verification_anchors": ["tests/scripts/test_planning_lifecycle.py"],
                        "open_questions": [],
                        "complexity_events": [],
                    },
                    "supplements": [],
                }
            ),
            encoding="utf-8",
        )
        write_greenfield_planning_artifacts(state)
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
        write_greenfield_planning_artifacts(state)
        repaired_issues = planning_lib.validate_phase_outputs(state, phase="convergence")

    assert any("ci_testing_baseline_expectations" in issue for issue in issues)
    assert repaired_issues == []


def test_approve_planning_ingests_execution_state():
    planning_lib = load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state("Ship the example plan"),
        "approval_ready",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        state = rebase_planning_state_paths(state, tmpdir)

        Path(state["approved_plan_path"]).write_text(PLAN_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        planning_lib.save_planning_state(state, planning_state_path)
        planning_lib.initialize_planning_artifacts(state)
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
