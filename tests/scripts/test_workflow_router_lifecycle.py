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
    example_plan,
    load_planning_lib,
    load_workflow_lib,
    load_workflow_router_lib,
    rebase_execution_state_paths,
    rebase_planning_state_paths,
    save_example_uat_artifact,
)


def test_workflow_router_start_planning_creates_artifacts():
    workflow_router = load_workflow_router_lib()

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
    workflow_router = load_workflow_router_lib()

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
    workflow_router = load_workflow_router_lib()

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
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(example_plan()), encoding="utf-8")

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
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(example_plan()), encoding="utf-8")

        active_state = rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md"),
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
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()

    replacement_plan = example_plan()
    replacement_plan["workflow_name"] = "Replacement workflow"

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(replacement_plan), encoding="utf-8")

        prior_state = rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="OLD.md"),
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
    planning_lib = load_planning_lib()
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        execution_state_path = Path(tmpdir) / "state.json"

        planning_state = rebase_planning_state_paths(
            planning_lib.build_planning_state("Approve a guarded planning session"),
            tmpdir,
        )
        planning_state = planning_lib.set_planning_status(planning_state, "approval_ready")
        planning_lib.save_planning_state(planning_state, planning_state_path)

        active_state = rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md"),
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
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()
    state = workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md")
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
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        execution_state_path = Path(tmpdir) / "state.json"
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state = rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md"),
            tmpdir,
        )
        state["workflow_status"] = "gap_closure_pending"
        state["steps"][0]["status"] = "implementing"
        workflow_lib.save_state(state, execution_state_path)
        save_example_uat_artifact(workflow_lib, state)
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
    workflow_lib = load_workflow_lib()
    workflow_router = load_workflow_router_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        execution_state_path = Path(tmpdir) / "state.json"
        planning_state_path = Path(tmpdir) / "planning_state.json"
        state = rebase_execution_state_paths(
            workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md"),
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
    workflow_router = load_workflow_router_lib()

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
