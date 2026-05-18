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


def _build_temp_planning_state(planning_lib, tmp_root: Path, *, planning_mode: str = "brownfield") -> dict:
    state = planning_lib.build_planning_state(
        "Plan a decision-complete workflow slice",
        planning_mode=planning_mode,
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
    return state


def _context_payload(
    feature_request: str,
    *,
    open_questions: list[str] | None = None,
    clarification_gate: dict | None = None,
    delivery_contract: dict | None = None,
) -> dict:
    return {
        "version": 1,
        "feature_request": feature_request,
        "delivery_contract": delivery_contract
        or {
            "mode": "one_shot",
            "comparison_required": False,
            "basis": "user request, repo context, and bounded clarification",
        },
        "goal": "Produce a decision-complete workflow plan.",
        "target_user": "Workflow maintainers",
        "desired_behavior": "The planner should resolve product-impacting ambiguity before planning.",
        "good_outcomes": [],
        "bad_outcomes": [],
        "locked_decisions": [],
        "defaults_taken": [],
        "open_questions": open_questions or [],
        "clarification_gate": clarification_gate
        or {
            "material_questions": [],
            "no_material_questions_reason": "No product-impacting ambiguity changes scope or verification.",
        },
        "constraints": [],
        "success_criteria": ["Planning can advance with an auditable discuss record."],
        "non_goals": [],
        "unresolved_risks": [],
    }


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


def test_direct_consumer_audit_honors_explicit_empty_matrix_row_without_fallback():
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
            "direct_verification_matrix": [
                {
                    "entry_point": entry_point,
                    "verification_targets": [],
                }
            ],
            "open_questions": [],
            "complexity_events": [],
        },
        "supplements": [],
    }

    issues = planning_lib.audit_plan_against_discovery(plan_spec, discovery)

    assert issues == []


def test_plan_contract_accepts_declared_validation_ownership_for_cross_step_verification():
    planning_lib = _load_planning_lib()
    entry_point = "app/workflows/release_notes.py"
    validation_target = "tests/workflows/test_release_regression.py"
    plan_spec = _compatibility_plan_for(
        entry_point,
        verify_cmds=[f"uv run pytest {validation_target}"],
    )
    plan_spec["steps"][0]["avoid_touching"] = ["app/workflows/execution.py"]
    plan_spec["steps"][0]["verification_targets"] = [validation_target]
    plan_spec["steps"][0]["validation_ownership"] = [validation_target]

    issues = planning_lib._audit_plan_contract(
        plan_spec,
        discovery={"current": {"entry_points": [], "pattern_anchors": []}},
        scope_contract={"deferred": []},
        architecture_constraints={"preserved_interfaces": []},
    )

    assert issues == []


def test_plan_contract_rejects_undeclared_cross_step_validation_target():
    planning_lib = _load_planning_lib()
    entry_point = "app/workflows/release_notes.py"
    validation_target = "tests/workflows/test_release_regression.py"
    plan_spec = _compatibility_plan_for(
        entry_point,
        verify_cmds=[f"uv run pytest {validation_target}"],
    )
    plan_spec["steps"][0]["avoid_touching"] = ["app/workflows/execution.py"]
    plan_spec["steps"][0]["verification_targets"] = [validation_target]

    issues = planning_lib._audit_plan_contract(
        plan_spec,
        discovery={"current": {"entry_points": [], "pattern_anchors": []}},
        scope_contract={"deferred": []},
        architecture_constraints={"preserved_interfaces": []},
    )

    assert issues == [
        "step step-1 verifies targets outside file_ownership without validation_ownership: "
        "tests/workflows/test_release_regression.py"
    ]


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
                    "delivery_contract": {
                        "mode": "one_shot",
                        "comparison_required": False,
                        "basis": "user request, repo context, and bounded clarification",
                    },
                    "goal": "Preserve a discovered consumer contract.",
                    "target_user": "Workflow maintainers",
                    "desired_behavior": "Discovery should reject malformed direct verification matrices.",
                    "good_outcomes": [],
                    "bad_outcomes": [],
                    "locked_decisions": [],
                    "defaults_taken": [],
                    "open_questions": [],
                    "clarification_gate": {
                        "material_questions": [],
                        "no_material_questions_reason": "The compatibility request is already narrow.",
                    },
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


def test_discuss_phase_requires_one_shot_delivery_contract():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_temp_planning_state(planning_lib, Path(tmpdir), planning_mode="greenfield")
        Path(state["context_path"]).write_text(
            json.dumps(
                _context_payload(
                    state["feature_request"],
                    delivery_contract={
                        "mode": "comparison_first",
                        "comparison_required": True,
                        "basis": "",
                    },
                )
            ),
            encoding="utf-8",
        )

        issues = planning_lib.validate_phase_outputs(state, phase="discuss")

    assert "context.delivery_contract.mode must be one_shot" in issues
    assert "context.delivery_contract.comparison_required must be false" in issues
    assert "context.delivery_contract.basis is required" in issues


def test_discuss_phase_accepts_legacy_context_without_new_contract_fields():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_temp_planning_state(planning_lib, Path(tmpdir))
        context = _context_payload(state["feature_request"])
        context.pop("delivery_contract")
        context.pop("clarification_gate")
        Path(state["context_path"]).write_text(json.dumps(context), encoding="utf-8")

        issues = planning_lib.validate_phase_outputs(state, phase="discuss")

    assert issues == []


def test_discuss_phase_requires_clarification_gate_for_material_questions():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_temp_planning_state(planning_lib, Path(tmpdir))
        Path(state["context_path"]).write_text(
            json.dumps(
                _context_payload(
                    state["feature_request"],
                    open_questions=["Should the dashboard use legal intake wording or generic CRM wording?"],
                    clarification_gate={
                        "material_questions": [
                            {
                                "question": "Should the dashboard use legal intake wording or generic CRM wording?",
                                "status": "defaulted",
                                "resolution": "Default to legal intake wording.",
                            }
                        ],
                        "no_material_questions_reason": "",
                    },
                )
            ),
            encoding="utf-8",
        )

        issues = planning_lib.validate_phase_outputs(state, phase="discuss")
        Path(state["context_path"]).write_text(
            json.dumps(
                _context_payload(
                    state["feature_request"],
                    clarification_gate={
                        "material_questions": [
                            {
                                "question": "Should the dashboard use legal intake wording or generic CRM wording?",
                                "recommended_answer": "Default to legal intake wording.",
                                "status": "defaulted",
                                "resolution": "Defaulted to legal intake wording because the request names that domain.",
                            }
                        ],
                        "no_material_questions_reason": "",
                    },
                )
            ),
            encoding="utf-8",
        )
        repaired_issues = planning_lib.validate_phase_outputs(state, phase="discuss")

    assert "context.open_questions must be resolved through clarification_gate before phase advance" in issues
    assert any("recommended_answer is required" in issue for issue in issues)
    assert repaired_issues == []


def test_discovery_phase_blocks_adopt_now_comparison_without_authoritative_baseline():
    planning_lib = _load_planning_lib()

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _build_temp_planning_state(planning_lib, Path(tmpdir))
        Path(state["context_path"]).write_text(
            json.dumps(_context_payload(state["feature_request"])),
            encoding="utf-8",
        )
        discovery = {
            "version": 1,
            "feature_request": state["feature_request"],
            "current": {
                "requirements": ["Produce a decision-complete workflow plan."],
                "anti_goals": [],
                "success_criteria": ["The comparison remains diagnostic unless the user makes it authoritative."],
                "entry_points": [],
                "blast_radius": [],
                "pattern_anchors": [],
                "verification_anchors": ["tests/scripts/test_planning_audit.py"],
                "comparison_diagnostic": {
                    "mode": "dogfood",
                    "source": "main branch comparison",
                    "baseline_authority": "diagnostic_only",
                    "findings": [
                        {
                            "classification": "adopt_now",
                            "summary": "Adopt the alternate option metadata endpoint.",
                            "rationale": "The comparison branch exposed a useful product direction.",
                        }
                    ],
                },
                "open_questions": [],
                "complexity_events": [],
            },
            "supplements": [],
        }
        Path(state["discovery_dossier_path"]).write_text(json.dumps(discovery), encoding="utf-8")

        issues = planning_lib.validate_phase_outputs(state, phase="discovery")
        discovery["current"]["comparison_diagnostic"]["baseline_authority"] = "authoritative"
        Path(state["discovery_dossier_path"]).write_text(json.dumps(discovery), encoding="utf-8")
        repaired_issues = planning_lib.validate_phase_outputs(state, phase="discovery")

    assert (
        "discovery current.comparison_diagnostic adopt_now findings require baseline_authority=authoritative"
        in issues
    )
    assert repaired_issues == []
