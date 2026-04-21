from __future__ import annotations

import importlib.util
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
STATE_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "state.example.json"
PLANNING_STATE_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "planning_state.example.json"
PLAN_EXAMPLE_PATH = REPO_ROOT / ".codex" / "workflow" / "plan.example.json"
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
    deferred: list[str] | None = None,
    open_questions: list[str] | None = None,
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
    assert state["context_path"].endswith("context.json")
    assert state["scope_contract_path"].endswith("scope_contract.json")
    assert state["architecture_constraints_path"].endswith("architecture_constraints.json")


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


def test_example_plan_builds_valid_state():
    workflow_lib = _load_workflow_lib()
    plan = json.loads(PLAN_EXAMPLE_PATH.read_text(encoding="utf-8"))

    state = workflow_lib.build_state_from_plan_spec(plan, plan_path=".codex/workflow/plan.example.json")

    workflow_lib.validate_state(state)
    assert state["current_step_id"] == "step-1"
    assert state["steps"][0]["status"] == "implementing"
    assert state["steps"][1]["status"] == "pending"
    assert state["steps"][1]["commit_message"] == "feature: land the follow-up slice"


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
    assert "python3 scripts/workflow_state.py set-step-status step-1 commit_pending" in decision.prompt
    assert "set-step-status step-1 commit_pending" in decision.prompt


def test_final_committed_step_enters_ship_pending_mode():
    workflow_lib = _load_workflow_lib()
    state = json.loads(STATE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    state["current_step_id"] = "step-2"
    state["steps"][0]["status"] = "committed"
    state["steps"][1]["status"] = "committed"

    new_state, decision, changed = workflow_lib.next_stop_decision(deepcopy(state))

    assert changed is True
    assert new_state["workflow_status"] == "ship_pending"
    assert decision.action == "block"
    assert "$ship" in decision.prompt


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
        context_exists = Path(state["context_path"]).exists()
        scope_exists = Path(state["scope_contract_path"]).exists()
        architecture_exists = Path(state["architecture_constraints_path"]).exists()

    assert response.status == "ok"
    assert response.mode == "planning"
    assert state["status"] == "discuss"
    assert context_exists is True
    assert scope_exists is True
    assert architecture_exists is True


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

    assert "python3 scripts/workflow_router.py planning-start" in skill_text
    assert ".codex/workflow/scripts/workflow_router.py" not in skill_text
    assert "Use $workflow" in metadata_text


def test_ship_skill_uses_bundled_workflow_state_wrapper():
    skill_text = SHIP_SKILL_PATH.read_text(encoding="utf-8")

    assert "python3 scripts/workflow_state.py set-step-status" in skill_text
    assert ".codex/workflow/scripts/workflow_state.py" not in skill_text


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


def test_planning_prompt_uses_bundled_planning_state_wrapper():
    planning_lib = _load_planning_lib()
    state = planning_lib.build_planning_state("Plan a plugin-safe workflow wrapper")

    prompt = planning_lib.planning_activation_prompt(state)

    assert "python3 scripts/planning_state.py audit-plan" in prompt
    assert ".codex/workflow/scripts/planning_state.py" not in prompt


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
        state["planning_trace_path"] = str(Path(tmpdir) / "planning_trace.json")

        planning_lib.save_planning_state(state, planning_state_path)
        planning_lib.initialize_planning_artifacts(state)

        context = json.loads(Path(state["context_path"]).read_text(encoding="utf-8"))
        discovery = json.loads(Path(state["discovery_dossier_path"]).read_text(encoding="utf-8"))
        scope_contract = json.loads(Path(state["scope_contract_path"]).read_text(encoding="utf-8"))
        architecture_constraints = json.loads(
            Path(state["architecture_constraints_path"]).read_text(encoding="utf-8")
        )
        trace = json.loads(Path(state["planning_trace_path"]).read_text(encoding="utf-8"))

    assert context["feature_request"] == "Add a planning workflow"
    assert context["goal"] == ""
    assert discovery["feature_request"] == "Add a planning workflow"
    assert discovery["current"]["entry_points"] == []
    assert scope_contract["must_have"] == []
    assert architecture_constraints["required_reuse"] == []
    assert trace["events"][0]["event"] == "planning_started"


def test_approve_planning_ingests_execution_state():
    planning_lib = _load_planning_lib()
    state = planning_lib.build_planning_state("Ship the example plan")
    state["status"] = "approval_ready"

    with tempfile.TemporaryDirectory() as tmpdir:
        planning_state_path = Path(tmpdir) / "planning_state.json"
        approved_plan_path = Path(tmpdir) / "approved-plan.json"
        execution_state_path = Path(tmpdir) / "state.json"
        context_path = Path(tmpdir) / "context.json"
        discovery_dossier_path = Path(tmpdir) / "discovery_dossier.json"
        scope_contract_path = Path(tmpdir) / "scope_contract.json"
        architecture_constraints_path = Path(tmpdir) / "architecture_constraints.json"
        planning_trace_path = Path(tmpdir) / "planning_trace.json"

        approved_plan_path.write_text(PLAN_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        state["approved_plan_path"] = str(approved_plan_path)
        state["context_path"] = str(context_path)
        state["discovery_dossier_path"] = str(discovery_dossier_path)
        state["scope_contract_path"] = str(scope_contract_path)
        state["architecture_constraints_path"] = str(architecture_constraints_path)
        state["planning_trace_path"] = str(planning_trace_path)

        planning_lib.save_planning_state(state, planning_state_path)
        planning_lib.initialize_planning_artifacts(state)
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=[
                "Example module public behavior contract",
                "Second example module public behavior contract",
            ],
        )

        execution_state = planning_lib.approve_planning(
            state,
            planning_state_path=planning_state_path,
            execution_state_path=execution_state_path,
        )

        persisted_state = json.loads(execution_state_path.read_text(encoding="utf-8"))

    assert execution_state["workflow_name"] == "Example feature rollout"
    assert persisted_state["current_step_id"] == "step-1"
    assert planning_state_path.exists() is False


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

        approved_plan_path.write_text(json.dumps(approved_plan), encoding="utf-8")
        discovery_dossier_path.write_text(json.dumps(discovery_dossier), encoding="utf-8")
        state["approved_plan_path"] = str(approved_plan_path)
        state["context_path"] = str(context_path)
        state["discovery_dossier_path"] = str(discovery_dossier_path)
        state["scope_contract_path"] = str(scope_contract_path)
        state["architecture_constraints_path"] = str(architecture_constraints_path)
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Current enrichment consumer interface"],
        )

        issues = planning_lib.audit_planning_artifacts(state)

    assert any("tests/api/test_ai_enrichment.py" in issue for issue in issues)
    assert any("tests/orchestrators/test_batch_enrichment.py" in issue for issue in issues)
    assert any("tests/orchestrators/test_filter_batch.py" in issue for issue in issues)


def test_approve_planning_rejects_underverified_compatibility_plan():
    planning_lib = _load_planning_lib()
    state = planning_lib.build_planning_state("Preserve compatibility for enrichment consumers")
    state["status"] = "approval_ready"

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
        planning_trace_path = Path(tmpdir) / "planning_trace.json"

        approved_plan_path.write_text(json.dumps(approved_plan), encoding="utf-8")
        discovery_dossier_path.write_text(json.dumps(discovery_dossier), encoding="utf-8")
        state["approved_plan_path"] = str(approved_plan_path)
        state["context_path"] = str(context_path)
        state["discovery_dossier_path"] = str(discovery_dossier_path)
        state["scope_contract_path"] = str(scope_contract_path)
        state["architecture_constraints_path"] = str(architecture_constraints_path)
        state["planning_trace_path"] = str(planning_trace_path)

        planning_lib.save_planning_state(state, planning_state_path)
        planning_lib.initialize_planning_artifacts(state)
        discovery_dossier_path.write_text(json.dumps(discovery_dossier), encoding="utf-8")
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Current enrichment consumer interface"],
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


def test_compare_plan_specs_reports_stronger_candidate():
    planning_lib = _load_planning_lib()
    baseline = _example_plan()
    for field_name in (
        "justification",
        "files_read_first",
        "interfaces_to_preserve",
        "avoid_touching",
        "verification_targets",
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
    candidate["steps"][0]["done_when"].append("Targeted regression coverage proves the contract did not drift.")
    candidate["steps"][0]["verify_cmds"].append("uv run pytest tests/ai/test_embedding_contract.py")

    comparison = planning_lib.compare_plan_specs(baseline, candidate)

    assert comparison["verdict"] == "stronger"
    assert any("step justification coverage" in item for item in comparison["improved"])
    assert any("read-first handoff coverage" in item for item in comparison["improved"])
    assert any("completion detail per step" in item for item in comparison["improved"])
    assert any("verification target breadth" in item for item in comparison["improved"])


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


def test_user_prompt_hook_ignores_normal_prompts():
    user_prompt_hook = _load_user_prompt_hook()

    request = user_prompt_hook.parse_workflow_request("implement the approved plan")

    assert request is None
