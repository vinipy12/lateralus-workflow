from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / ".codex" / "workflow" / "scripts"
PLANNING_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "planning_lib.py"


if str(WORKFLOW_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS_DIR))


def _load_planning_lib():
    spec = importlib.util.spec_from_file_location("codex_planning_audit_lib", PLANNING_LIB_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _compatibility_plan_for(entry_point: str, *, verify_cmds: list[str]) -> dict:
    return {
        "workflow_name": "Compatibility coverage",
        "summary": "Preserve a discovered consumer contract.",
        "requirements": [
            {
                "id": "R1",
                "kind": "verification",
                "text": "Verify the discovered consumer contract directly.",
            }
        ],
        "assumptions": [],
        "open_questions": [],
        "out_of_scope": [],
        "steps": [
            {
                "id": "step-1",
                "title": "Prove direct consumer compatibility",
                "goal": "Validate that the refactor preserves the current consumer interface.",
                "requirement_ids": ["R1"],
                "context": [entry_point],
                "planned_updates": [entry_point],
                "planned_creates": [],
                "constraints": ["Keep this step compatibility-focused."],
                "justification": "This step proves that the refactor does not break direct consumers.",
                "files_read_first": [entry_point],
                "interfaces_to_preserve": ["Current consumer interface"],
                "avoid_touching": [],
                "verification_targets": [],
                "risk_flags": ["Preserve the current consumer interface."],
                "blast_radius": [f"{entry_point} consumers"],
                "decision_ids": ["D-COMPAT-1"],
                "depends_on": [],
                "wave": 1,
                "file_ownership": [entry_point],
                "rollback_notes": ["Revert the compatibility step if the consumer contract regresses."],
                "operational_watchpoints": ["Watch direct consumer verification while the refactor lands."],
                "done_when": ["Existing consumers remain compatible."],
                "verify_cmds": verify_cmds,
                "commit_message": "refactor: preserve consumer compatibility",
            }
        ],
    }


def test_direct_consumer_audit_uses_explicit_verification_matrix():
    planning_lib = _load_planning_lib()
    entry_point = "app/integrations/reporting_adapter.py"
    direct_target = "tests/contracts/test_reporting_adapter_consumer.py"
    plan_spec = _compatibility_plan_for(
        entry_point,
        verify_cmds=["uv run pytest tests/e2e/test_reporting_flow.py"],
    )
    discovery = {
        "version": 1,
        "feature_request": "Preserve reporting consumer compatibility",
        "current": {
            "requirements": [],
            "anti_goals": [],
            "success_criteria": [],
            "entry_points": [entry_point],
            "blast_radius": [f"{entry_point} consumers depend on the current behavior contract."],
            "pattern_anchors": [],
            "verification_anchors": [],
            "direct_verification_matrix": [
                {
                    "entry_point": entry_point,
                    "verification_targets": [direct_target],
                }
            ],
            "open_questions": [],
            "complexity_events": [],
        },
        "supplements": [],
    }

    issues = planning_lib.audit_plan_against_discovery(plan_spec, discovery)

    assert any(direct_target in issue for issue in issues)


def test_direct_consumer_audit_flags_unmapped_consumers_without_matrix():
    planning_lib = _load_planning_lib()
    entry_point = "app/integrations/nonstandard/reporting_adapter.py"
    plan_spec = _compatibility_plan_for(
        entry_point,
        verify_cmds=["uv run pytest tests/e2e/test_reporting_flow.py"],
    )
    discovery = {
        "version": 1,
        "feature_request": "Preserve reporting consumer compatibility",
        "current": {
            "requirements": [],
            "anti_goals": [],
            "success_criteria": [],
            "entry_points": [entry_point],
            "blast_radius": [f"{entry_point} consumers depend on the current behavior contract."],
            "pattern_anchors": [],
            "verification_anchors": [],
            "open_questions": [],
            "complexity_events": [],
        },
        "supplements": [],
    }

    issues = planning_lib.audit_plan_against_discovery(plan_spec, discovery)

    assert any("no direct verification target mapping" in issue for issue in issues)
    assert any(entry_point in issue for issue in issues)


def test_direct_consumer_audit_rejects_matrix_without_entry_points():
    planning_lib = _load_planning_lib()
    entry_point = "app/integrations/reporting_adapter.py"
    direct_target = "tests/contracts/test_reporting_adapter_consumer.py"
    plan_spec = _compatibility_plan_for(
        entry_point,
        verify_cmds=[f"uv run pytest {direct_target}"],
    )
    discovery = {
        "version": 1,
        "feature_request": "Preserve reporting consumer compatibility",
        "current": {
            "requirements": [],
            "anti_goals": [],
            "success_criteria": [],
            "entry_points": [],
            "blast_radius": [f"{entry_point} consumers depend on the current behavior contract."],
            "pattern_anchors": [],
            "verification_anchors": [],
            "direct_verification_matrix": [
                {
                    "entry_point": entry_point,
                    "verification_targets": [direct_target],
                }
            ],
            "open_questions": [],
            "complexity_events": [],
        },
        "supplements": [],
    }

    issues = planning_lib.audit_plan_against_discovery(plan_spec, discovery)

    assert issues == ["discovery current.direct_verification_matrix requires non-empty current.entry_points"]


def test_discovery_phase_rejects_matrix_without_entry_points():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        state = planning_lib.build_planning_state(
            "Preserve reporting consumer compatibility",
            context_path=str(tmp_root / "context.json"),
            discovery_dossier_path=str(tmp_root / "discovery_dossier.json"),
            scope_contract_path=str(tmp_root / "scope_contract.json"),
            architecture_constraints_path=str(tmp_root / "architecture_constraints.json"),
            product_scope_audit_path=str(tmp_root / "product_scope_audit.json"),
            skeptic_audit_path=str(tmp_root / "skeptic_audit.json"),
            convergence_summary_path=str(tmp_root / "convergence_summary.json"),
            approved_plan_path=str(tmp_root / "approved-plan.json"),
            planning_trace_path=str(tmp_root / "planning_trace.json"),
            stack_runtime_decision_path=str(tmp_root / "stack_runtime_decision.json"),
            bootstrap_expectations_path=str(tmp_root / "bootstrap_expectations.json"),
            project_memory_path=str(tmp_root / "PROJECT.md"),
            requirements_memory_path=str(tmp_root / "REQUIREMENTS.md"),
            state_memory_path=str(tmp_root / "STATE.md"),
        )
        planning_lib.initialize_planning_artifacts(state)
        Path(state["context_path"]).write_text(
            json.dumps(
                {
                    "version": 1,
                    "feature_request": state["feature_request"],
                    "goal": "Preserve a discovered consumer contract.",
                    "target_user": "Workflow maintainers",
                    "desired_behavior": "Discovery should reject malformed direct verification matrices.",
                    "good_outcomes": [],
                    "bad_outcomes": [],
                    "locked_decisions": [],
                    "defaults_taken": [],
                    "open_questions": [],
                    "constraints": [],
                    "success_criteria": ["Discovery catches malformed compatibility metadata."],
                    "non_goals": [],
                    "unresolved_risks": [],
                }
            ),
            encoding="utf-8",
        )
        Path(state["discovery_dossier_path"]).write_text(
            json.dumps(
                {
                    "version": 1,
                    "feature_request": state["feature_request"],
                    "current": {
                        "requirements": ["Preserve reporting consumer compatibility."],
                        "assumptions": [],
                        "anti_goals": [],
                        "success_criteria": ["The reporting consumer contract remains explicit and auditable."],
                        "entry_points": [],
                        "blast_radius": ["Reporting consumers depend on the current behavior contract."],
                        "pattern_anchors": [],
                        "verification_anchors": [],
                        "direct_verification_matrix": [
                            {
                                "entry_point": "app/integrations/reporting_adapter.py",
                                "verification_targets": ["tests/contracts/test_reporting_adapter_consumer.py"],
                            }
                        ],
                        "open_questions": [],
                        "complexity_events": [],
                    },
                    "supplements": [],
                }
            ),
            encoding="utf-8",
        )

        issues = planning_lib.validate_phase_outputs(state, phase="discovery")

    assert "discovery phase direct_verification_matrix requires non-empty current.entry_points" in issues
