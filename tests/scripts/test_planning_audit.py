from __future__ import annotations

import importlib.util
import sys
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
