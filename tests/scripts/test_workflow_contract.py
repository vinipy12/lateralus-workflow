from __future__ import annotations

import json
import sys
import tempfile
from copy import deepcopy
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
    STATE_EXAMPLE_PATH,
    example_plan,
    load_workflow_lib,
)


def test_example_state_is_valid():
    workflow_lib = load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    workflow_lib.validate_state(state)


def test_example_plan_builds_valid_state():
    workflow_lib = load_workflow_lib()
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
    assert state["steps"][1]["validation_ownership"] == ["tests/example/test_module.py"]
    assert state["uat_artifact_path"] == ".codex/workflow/uat.json"
    assert state["metrics_dir"] == ".codex/workflow/metrics"


def test_plan_inference_adds_relevant_agents_paths():
    workflow_lib = load_workflow_lib()

    state = workflow_lib.build_state_from_plan_spec(example_plan(), plan_path="PLANS.md")

    assert state["steps"][0]["agents_paths"] == ["AGENTS.md"]


def test_plan_validation_requires_requirement_coverage():
    workflow_lib = load_workflow_lib()
    plan = example_plan()
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
    workflow_lib = load_workflow_lib()
    plan = example_plan()
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
    workflow_lib = load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["steps"][0]["status"] = "committed"

    new_state, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is True
    assert decision.action == "block"
    assert new_state["current_step_id"] == "step-2"
    assert new_state["steps"][1]["status"] == "implementing"
    assert "step-2" in decision.prompt


def test_activation_prompt_renders_execution_handoff_fields():
    workflow_lib = load_workflow_lib()
    plan = example_plan()
    plan["steps"][0]["validation_ownership"] = ["tests/ai/test_embedding_contract.py"]
    state = workflow_lib.build_state_from_plan_spec(plan, plan_path="PLANS.md")

    prompt = workflow_lib.activation_prompt(state)

    assert "Justification:\nThis keeps the change isolated to the embedding service." in prompt
    assert "Files to read first:\n- app/ai/embedding/service.py" in prompt
    assert "Interfaces to preserve:\n- Embedding service public behavior" in prompt
    assert "Avoid touching:\n- app/api/embedding.py" in prompt
    assert "Verification targets:\n- tests/ai/test_embedding_service.py" in prompt
    assert "Validation ownership:\n- tests/ai/test_embedding_contract.py" in prompt
    assert "Risk flags:\n- Preserve existing embedding output shape for current consumers." in prompt
    assert "Blast radius:\n- app/ai/embedding/service.py consumers" in prompt
    assert "Decision IDs:\n- D-EMBED-1" in prompt
    assert "Wave:\n1" in prompt
    assert "Depends on:\n- none" not in prompt
    assert "Owned files:\n- app/ai/embedding/service.py" in prompt
    assert "Rollback notes:\n- Revert the embedding behavior commit if current consumers regress." in prompt
    assert "Operational watchpoints:\n- Watch the embedding service public behavior contract during verification." in prompt
    assert "Update `STATE.md`" in prompt


def test_markdown_plan_file_can_be_selected_by_plan_id():
    workflow_lib = load_workflow_lib()
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
