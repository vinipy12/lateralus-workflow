from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROUTER_CLI_PATH = REPO_ROOT / ".codex" / "workflow" / "scripts" / "workflow_router.py"
WORKFLOW_ROUTER_SKILL_SCRIPT_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "scripts" / "workflow_router.py"


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


def test_execution_start_honors_custom_planning_state_path():
    plan = _example_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow_root = Path(tmpdir) / "custom-workflow"
        planning_state_path = workflow_root / "planning_state.json"
        execution_state_path = workflow_root / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        planning_result = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_ROUTER_CLI_PATH),
                "--json",
                "planning-start",
                "Plan a split-path execution guard",
                "--planning-state-path",
                str(planning_state_path),
                "--execution-state-path",
                str(execution_state_path),
            ],
            cwd=tmpdir,
            check=False,
            capture_output=True,
            text=True,
        )

        result = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_ROUTER_CLI_PATH),
                "--json",
                "execution-start",
                str(plan_path),
                "--planning-state-path",
                str(planning_state_path),
                "--execution-state-path",
                str(execution_state_path),
            ],
            cwd=tmpdir,
            check=False,
            capture_output=True,
            text=True,
        )

    assert planning_result.returncode == 0, planning_result.stderr
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "planning-approve" in payload["message"]


def test_workflow_skill_router_execution_start_writes_custom_execution_root():
    plan = _example_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow_root = Path(tmpdir) / "custom-workflow"
        planning_state_path = workflow_root / "planning_state.json"
        execution_state_path = workflow_root / "state.json"
        plan_path = Path(tmpdir) / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW_ROUTER_SKILL_SCRIPT_PATH),
                "--json",
                "execution-start",
                str(plan_path),
                "--planning-state-path",
                str(planning_state_path),
                "--execution-state-path",
                str(execution_state_path),
            ],
            cwd=tmpdir,
            check=False,
            capture_output=True,
            text=True,
        )

        default_state_path = Path(tmpdir) / ".codex" / "workflow" / "state.json"
        payload = json.loads(result.stdout)
        state = json.loads(execution_state_path.read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert payload["status"] == "ok"
    assert state["workflow_name"] == plan["workflow_name"]
    assert state["plan_path"] == plan_path.name
    assert state["uat_artifact_path"] == str(workflow_root / "uat.json")
    assert state["metrics_dir"] == str(workflow_root / "metrics")
    assert default_state_path.exists() is False
