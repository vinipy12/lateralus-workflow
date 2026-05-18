from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / ".codex" / "workflow" / "scripts"
PLANNING_LIB_PATH = WORKFLOW_SCRIPTS_DIR / "planning_lib.py"


if str(WORKFLOW_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS_DIR))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_planning_lib():
    return _load_module("codex_planning_audit_integration_lib", PLANNING_LIB_PATH)


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


def _write_supporting_planning_artifacts(
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
                "delivery_contract": {
                    "mode": "one_shot",
                    "comparison_required": False,
                    "basis": "user request, repo context, and bounded clarification",
                },
                "goal": "Ship a decision-complete plan.",
                "target_user": "Workflow maintainers",
                "desired_behavior": "The planner should produce a safe, implementable plan.",
                "good_outcomes": ["The implementer can follow the plan directly."],
                "bad_outcomes": ["The plan leaves architecture or verification decisions open."],
                "locked_decisions": ["Keep planning artifacts JSON-first."],
                "defaults_taken": ["Prefer the smallest viable slice."],
                "open_questions": open_questions or [],
                "clarification_gate": {
                    "material_questions": [],
                    "no_material_questions_reason": "The request is narrow enough to plan without changing product scope.",
                },
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


def _rebase_planning_state_paths(state: dict, tmpdir: str) -> dict:
    tmp_root = Path(tmpdir)
    rebased = dict(state)
    rebased["approved_plan_path"] = str(tmp_root / "approved-plan.json")
    rebased["context_path"] = str(tmp_root / "context.json")
    rebased["discovery_dossier_path"] = str(tmp_root / "discovery_dossier.json")
    rebased["scope_contract_path"] = str(tmp_root / "scope_contract.json")
    rebased["architecture_constraints_path"] = str(tmp_root / "architecture_constraints.json")
    rebased["product_scope_audit_path"] = str(tmp_root / "product_scope_audit.json")
    rebased["skeptic_audit_path"] = str(tmp_root / "skeptic_audit.json")
    rebased["convergence_summary_path"] = str(tmp_root / "convergence_summary.json")
    rebased["stack_runtime_decision_path"] = str(tmp_root / "stack_runtime_decision.json")
    rebased["bootstrap_expectations_path"] = str(tmp_root / "bootstrap_expectations.json")
    rebased["planning_trace_path"] = str(tmp_root / "planning_trace.json")
    rebased["project_memory_path"] = str(tmp_root / "PROJECT.md")
    rebased["requirements_memory_path"] = str(tmp_root / "REQUIREMENTS.md")
    rebased["state_memory_path"] = str(tmp_root / "STATE.md")
    return rebased


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
                "risk_flags": ["Preserve the current enrichment consumer interface."],
                "blast_radius": [
                    "app/api/ai_enrichment.py consumers",
                    "app/orchestrators/batch_enrichment.py consumers",
                    "app/orchestrators/filter_batch.py consumers",
                ],
                "decision_ids": ["D-COMPAT-1"],
                "depends_on": [],
                "wave": 1,
                "file_ownership": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "rollback_notes": ["Revert the compatibility step if any consumer contract regresses."],
                "operational_watchpoints": [
                    "Watch direct enrichment consumer tests while the refactor lands."
                ],
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
            "direct_verification_matrix": [
                {
                    "entry_point": "app/api/ai_enrichment.py",
                    "verification_targets": ["tests/contracts/test_ai_enrichment_route.py"],
                },
                {
                    "entry_point": "app/orchestrators/batch_enrichment.py",
                    "verification_targets": ["tests/contracts/test_batch_enrichment_orchestrator.py"],
                },
                {
                    "entry_point": "app/orchestrators/filter_batch.py",
                    "verification_targets": ["tests/contracts/test_filter_batch_orchestrator.py"],
                },
            ],
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
        product_scope_audit_path = Path(tmpdir) / "product_scope_audit.json"
        skeptic_audit_path = Path(tmpdir) / "skeptic_audit.json"
        convergence_summary_path = Path(tmpdir) / "convergence_summary.json"
        planning_trace_path = Path(tmpdir) / "planning_trace.json"
        project_memory_path = Path(tmpdir) / "PROJECT.md"
        requirements_memory_path = Path(tmpdir) / "REQUIREMENTS.md"
        state_memory_path = Path(tmpdir) / "STATE.md"

        approved_plan_path.write_text(json.dumps(approved_plan), encoding="utf-8")
        discovery_dossier_path.write_text(json.dumps(discovery_dossier), encoding="utf-8")
        state["approved_plan_path"] = str(approved_plan_path)
        state["context_path"] = str(context_path)
        state["discovery_dossier_path"] = str(discovery_dossier_path)
        state["scope_contract_path"] = str(scope_contract_path)
        state["architecture_constraints_path"] = str(architecture_constraints_path)
        state["product_scope_audit_path"] = str(product_scope_audit_path)
        state["skeptic_audit_path"] = str(skeptic_audit_path)
        state["convergence_summary_path"] = str(convergence_summary_path)
        state["planning_trace_path"] = str(planning_trace_path)
        state["project_memory_path"] = str(project_memory_path)
        state["requirements_memory_path"] = str(requirements_memory_path)
        state["state_memory_path"] = str(state_memory_path)
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Current enrichment consumer interface"],
            active_initiative="Keep the existing enrichment consumers compatible during a refactor.",
        )

        issues = planning_lib.audit_planning_artifacts(state)

    assert any("tests/contracts/test_ai_enrichment_route.py" in issue for issue in issues)
    assert any("tests/contracts/test_batch_enrichment_orchestrator.py" in issue for issue in issues)
    assert any("tests/contracts/test_filter_batch_orchestrator.py" in issue for issue in issues)


def test_approve_planning_rejects_underverified_compatibility_plan():
    planning_lib = _load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state("Preserve compatibility for enrichment consumers"),
        "approval_ready",
    )

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
                "risk_flags": ["Preserve the current enrichment consumer interface."],
                "blast_radius": [
                    "app/api/ai_enrichment.py consumers",
                    "app/orchestrators/batch_enrichment.py consumers",
                    "app/orchestrators/filter_batch.py consumers",
                ],
                "decision_ids": ["D-COMPAT-1"],
                "depends_on": [],
                "wave": 1,
                "file_ownership": [
                    "app/api/ai_enrichment.py",
                    "app/orchestrators/batch_enrichment.py",
                    "app/orchestrators/filter_batch.py",
                ],
                "rollback_notes": ["Revert the compatibility step if any consumer contract regresses."],
                "operational_watchpoints": [
                    "Watch direct enrichment consumer tests while the refactor lands."
                ],
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
            "direct_verification_matrix": [
                {
                    "entry_point": "app/api/ai_enrichment.py",
                    "verification_targets": ["tests/contracts/test_ai_enrichment_route.py"],
                },
                {
                    "entry_point": "app/orchestrators/batch_enrichment.py",
                    "verification_targets": ["tests/contracts/test_batch_enrichment_orchestrator.py"],
                },
                {
                    "entry_point": "app/orchestrators/filter_batch.py",
                    "verification_targets": ["tests/contracts/test_filter_batch_orchestrator.py"],
                },
            ],
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
        product_scope_audit_path = Path(tmpdir) / "product_scope_audit.json"
        skeptic_audit_path = Path(tmpdir) / "skeptic_audit.json"
        convergence_summary_path = Path(tmpdir) / "convergence_summary.json"
        planning_trace_path = Path(tmpdir) / "planning_trace.json"
        project_memory_path = Path(tmpdir) / "PROJECT.md"
        requirements_memory_path = Path(tmpdir) / "REQUIREMENTS.md"
        state_memory_path = Path(tmpdir) / "STATE.md"

        approved_plan_path.write_text(json.dumps(approved_plan), encoding="utf-8")
        discovery_dossier_path.write_text(json.dumps(discovery_dossier), encoding="utf-8")
        state["approved_plan_path"] = str(approved_plan_path)
        state["context_path"] = str(context_path)
        state["discovery_dossier_path"] = str(discovery_dossier_path)
        state["scope_contract_path"] = str(scope_contract_path)
        state["architecture_constraints_path"] = str(architecture_constraints_path)
        state["product_scope_audit_path"] = str(product_scope_audit_path)
        state["skeptic_audit_path"] = str(skeptic_audit_path)
        state["convergence_summary_path"] = str(convergence_summary_path)
        state["planning_trace_path"] = str(planning_trace_path)
        state["project_memory_path"] = str(project_memory_path)
        state["requirements_memory_path"] = str(requirements_memory_path)
        state["state_memory_path"] = str(state_memory_path)

        planning_lib.save_planning_state(state, planning_state_path)
        planning_lib.initialize_planning_artifacts(state)
        discovery_dossier_path.write_text(json.dumps(discovery_dossier), encoding="utf-8")
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Current enrichment consumer interface"],
            active_initiative="Keep the existing enrichment consumers compatible during a refactor.",
        )

        try:
            planning_lib.approve_planning(
                state,
                planning_state_path=planning_state_path,
                execution_state_path=execution_state_path,
            )
        except ValueError as exc:
            assert "failed planning audit" in str(exc)
            assert "tests/contracts/test_ai_enrichment_route.py" in str(exc)
        else:
            raise AssertionError("expected approve_planning to reject under-verified compatibility plan")


def test_convergence_cannot_advance_to_approval_ready_while_audit_is_dirty():
    planning_lib = _load_planning_lib()
    state = planning_lib.set_planning_status(
        planning_lib.build_planning_state("Guard the final approval gate"),
        "convergence",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_planning_state_paths(state, tmpdir)
        approved_plan_path = Path(state["approved_plan_path"])
        approved_plan_path.write_text(json.dumps(_example_plan()), encoding="utf-8")
        planning_lib.initialize_planning_artifacts(state)
        Path(state["discovery_dossier_path"]).write_text(
            json.dumps(
                {
                    "version": 1,
                    "feature_request": state["feature_request"],
                    "current": {
                        "requirements": ["Update the embedding behavior."],
                        "anti_goals": [],
                        "success_criteria": ["The embedding flow uses the updated behavior."],
                        "entry_points": ["app/ai/embedding/service.py"],
                        "blast_radius": ["Embedding service consumers depend on the current output shape."],
                        "pattern_anchors": [],
                        "verification_anchors": ["tests/ai/test_embedding_service.py"],
                        "open_questions": [],
                        "complexity_events": [],
                    },
                    "supplements": [],
                }
            ),
            encoding="utf-8",
        )
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Embedding service public behavior"],
            active_initiative="A different initiative that should fail the memory audit.",
        )

        try:
            planning_lib.advance_planning_phase(state, target_status="approval_ready")
        except ValueError as exc:
            assert "STATE.md" in str(exc)
        else:
            raise AssertionError("expected approval_ready advancement to enforce the final audit gate")


def test_repo_memory_drift_detection_flags_deferred_scope_leaks():
    planning_lib = _load_planning_lib()
    state = planning_lib.build_planning_state("Protect repo memory from drift")

    with tempfile.TemporaryDirectory() as tmpdir:
        state = _rebase_planning_state_paths(state, tmpdir)
        approved_plan_path = Path(state["approved_plan_path"])
        approved_plan_path.write_text(json.dumps(_example_plan()), encoding="utf-8")
        Path(state["discovery_dossier_path"]).write_text(
            json.dumps(
                {
                    "version": 1,
                    "feature_request": state["feature_request"],
                    "current": {
                        "requirements": ["Update the embedding behavior."],
                        "anti_goals": [],
                        "success_criteria": ["The embedding flow uses the updated behavior."],
                        "entry_points": ["app/ai/embedding/service.py"],
                        "blast_radius": ["Embedding service consumers depend on the current output shape."],
                        "pattern_anchors": [],
                        "verification_anchors": ["tests/ai/test_embedding_service.py"],
                        "open_questions": [],
                        "complexity_events": [],
                    },
                    "supplements": [],
                }
            ),
            encoding="utf-8",
        )
        _write_supporting_planning_artifacts(
            state,
            preserved_interfaces=["Embedding service public behavior"],
            deferred=["embedding behavior"],
            active_initiative="Update the embedding flow in one verified step.",
        )

        issues = planning_lib.audit_planning_artifacts(state)

    assert any("REQUIREMENTS.md" in issue for issue in issues)
    assert any("embedding behavior" in issue for issue in issues)
