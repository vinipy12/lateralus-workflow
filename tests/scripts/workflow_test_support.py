from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / ".codex" / "workflow" / "scripts"
WORKFLOW_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "workflow_lib.py"
PLANNING_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "planning_lib.py"
WORKFLOW_ROUTER_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "workflow_router_lib.py"
WORKFLOW_STATE_CLI_PATH = WORKFLOW_SCRIPTS_DIR / "workflow_state.py"
METRICS_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "metrics_lib.py"
STATE_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "state.example.json"
PLAN_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "plan.example.json"


if str(WORKFLOW_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS_DIR))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_workflow_lib():
    return load_module("codex_workflow_lib_support", WORKFLOW_LIB_PATH)


def load_planning_lib():
    return load_module("codex_planning_lib_support", PLANNING_LIB_PATH)


def load_workflow_router_lib():
    return load_module("codex_workflow_router_lib_support", WORKFLOW_ROUTER_LIB_PATH)


def load_metrics_lib():
    return load_module("codex_metrics_lib_support", METRICS_LIB_PATH)


def example_plan() -> dict:
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


def write_supporting_planning_artifacts(
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


def rebase_execution_state_paths(state: dict, tmpdir: str) -> dict:
    tmp_root = Path(tmpdir)
    rebased = deepcopy(state)
    rebased["uat_artifact_path"] = str(tmp_root / "uat.json")
    rebased["metrics_dir"] = str(tmp_root / "metrics")
    return rebased


def save_example_uat_artifact(workflow_lib, state: dict, *, plan_spec: dict | None = None) -> None:
    workflow_lib.save_uat_artifact(
        workflow_lib.build_uat_artifact(
            plan_spec or example_plan(),
            workflow_name=state["workflow_name"],
            plan_path=state["plan_path"],
            project_memory_path="PROJECT.md",
            requirements_memory_path="REQUIREMENTS.md",
            state_memory_path="STATE.md",
        ),
        Path(state["uat_artifact_path"]),
    )


def run_workflow_state_command(state_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(WORKFLOW_STATE_CLI_PATH),
            *args,
            "--path",
            str(state_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
