from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


TESTS_SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
NEXT_STEPS_PATH = REPO_ROOT / "next-steps.md"
WORKFLOW_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "SKILL.md"
WORKFLOW_SKILL_OPENAI_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "agents" / "openai.yaml"
WORKFLOW_ROUTER_SKILL_SCRIPT_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "scripts" / "workflow_router.py"
PLANNING_STATE_SKILL_SCRIPT_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "scripts" / "planning_state.py"
WORKFLOW_STATE_SKILL_SCRIPT_PATH = REPO_ROOT / ".agents" / "skills" / "workflow" / "scripts" / "workflow_state.py"
WORKFLOW_ALIAS_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "lateralus-workflow" / "SKILL.md"
WORKFLOW_ALIAS_ROUTER_SCRIPT_PATH = (
    REPO_ROOT / ".agents" / "skills" / "lateralus-workflow" / "scripts" / "workflow_router.py"
)
SHIP_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "ship" / "SKILL.md"
SHIP_WORKFLOW_STATE_SKILL_SCRIPT_PATH = REPO_ROOT / ".agents" / "skills" / "ship" / "scripts" / "workflow_state.py"
PLUGIN_MANIFEST_PATH = REPO_ROOT / ".codex-plugin" / "plugin.json"


if str(TESTS_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_SCRIPTS_DIR))


from workflow_test_support import example_plan, load_planning_lib  # noqa: E402


def test_workflow_skill_router_wrapper_blocks_execution_activation_while_planning_exists():
    plan = example_plan()

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


def test_workflow_skill_is_scaffolded():
    assert WORKFLOW_SKILL_PATH.exists()
    assert WORKFLOW_SKILL_OPENAI_PATH.exists()
    assert WORKFLOW_ROUTER_SKILL_SCRIPT_PATH.exists()
    assert PLANNING_STATE_SKILL_SCRIPT_PATH.exists()
    assert WORKFLOW_STATE_SKILL_SCRIPT_PATH.exists()
    assert WORKFLOW_ALIAS_SKILL_PATH.exists()
    assert WORKFLOW_ALIAS_ROUTER_SCRIPT_PATH.exists()
    assert SHIP_SKILL_PATH.exists()
    assert SHIP_WORKFLOW_STATE_SKILL_SCRIPT_PATH.exists()

    skill_text = WORKFLOW_SKILL_PATH.read_text(encoding="utf-8")
    metadata_text = WORKFLOW_SKILL_OPENAI_PATH.read_text(encoding="utf-8")

    assert "python3 scripts/workflow_router.py planning-start" in skill_text
    assert "python3 scripts/workflow_router.py bootstrap-start" in skill_text
    assert "python3 scripts/workflow_state.py set-uat-status" in skill_text
    assert "Deployment begins only after UAT moves the workflow to `ship_pending`." in skill_text
    assert ".agents/skills/workflow/scripts/workflow_router.py" not in skill_text
    assert "Use $workflow" in metadata_text


def test_lateralus_workflow_alias_skill_routes_to_workflow_contract():
    alias_text = WORKFLOW_ALIAS_SKILL_PATH.read_text(encoding="utf-8")

    assert "name: lateralus-workflow" in alias_text
    assert "$lateralus-workflow:" in alias_text
    assert "Use the same contract as `$workflow`" in alias_text
    assert "python3 scripts/workflow_router.py planning-start" in alias_text

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, str(WORKFLOW_ALIAS_ROUTER_SCRIPT_PATH), "--json", "status"],
            cwd=tmpdir,
            check=False,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["message"] == "no active workflow state"


def test_ship_skill_uses_bundled_workflow_state_wrapper():
    skill_text = SHIP_SKILL_PATH.read_text(encoding="utf-8")

    assert "python3 scripts/workflow_state.py set-step-status" in skill_text
    assert "ship_pending" in skill_text
    assert "user explicitly asked to ship anyway" not in skill_text
    assert ".agents/skills/ship/scripts/workflow_state.py" not in skill_text


def test_readme_and_next_steps_reflect_new_surface():
    readme_text = README_PATH.read_text(encoding="utf-8")
    next_steps_text = NEXT_STEPS_PATH.read_text(encoding="utf-8")

    assert "bootstrap-start" in readme_text
    assert "set-uat-status" in readme_text
    assert "set-workflow-status <status> --override-reason" in readme_text
    assert ".codex/workflow/metrics/" in readme_text
    assert "$lateralus-workflow" in readme_text
    assert "scripts/lateralus_plugin.py install" in readme_text
    assert "./.codex/plugins/lateralus-workflow" in readme_text
    assert "uv run pytest tests/scripts/" in readme_text
    assert "Current Repo State" in next_steps_text
    assert "Distance To Production Ready" in next_steps_text
    assert "This repo is still not close to production ready." in next_steps_text
    assert "Production-Ready Means" in next_steps_text
    assert "Milestone 1: Kernel Stabilization" in next_steps_text
    assert "Production rollout orchestration beyond PR shipping." in next_steps_text
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
    plan = example_plan()

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
    planning_lib = load_planning_lib()
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
    assert any("$lateralus-workflow" in prompt for prompt in manifest["interface"]["defaultPrompt"])
