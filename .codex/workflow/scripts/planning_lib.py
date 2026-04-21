from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workflow_lib import (
    DEFAULT_STATE_PATH,
    _ensure_string_list,
    _looks_like_repo_path,
    build_state_from_plan_spec,
    load_plan_spec,
    save_state,
    validate_plan_spec,
)


ROOT_DIR = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PLANNING_STATE_PATH = WORKFLOW_DIR / "planning_state.json"
DEFAULT_APPROVED_PLAN_PATH = WORKFLOW_DIR / "approved-plan.json"
DEFAULT_CONTEXT_PATH = WORKFLOW_DIR / "context.json"
DEFAULT_DISCOVERY_DOSSIER_PATH = WORKFLOW_DIR / "discovery_dossier.json"
DEFAULT_SCOPE_CONTRACT_PATH = WORKFLOW_DIR / "scope_contract.json"
DEFAULT_ARCHITECTURE_CONSTRAINTS_PATH = WORKFLOW_DIR / "architecture_constraints.json"
DEFAULT_PRODUCT_SCOPE_AUDIT_PATH = WORKFLOW_DIR / "product_scope_audit.json"
DEFAULT_SKEPTIC_AUDIT_PATH = WORKFLOW_DIR / "skeptic_audit.json"
DEFAULT_CONVERGENCE_SUMMARY_PATH = WORKFLOW_DIR / "convergence_summary.json"
DEFAULT_PLANNING_TRACE_PATH = WORKFLOW_DIR / "planning_trace.json"
DEFAULT_V0_PLAN_BASELINE_PATH = WORKFLOW_DIR / "approved-plan-v0.json"
DEFAULT_V0_DISCOVERY_BASELINE_PATH = WORKFLOW_DIR / "discovery-dossier-v0.json"
DEFAULT_PROJECT_MEMORY_PATH = ROOT_DIR / "PROJECT.md"
DEFAULT_REQUIREMENTS_MEMORY_PATH = ROOT_DIR / "REQUIREMENTS.md"
DEFAULT_STATE_MEMORY_PATH = ROOT_DIR / "STATE.md"
SKILL_SCRIPTS_DIR = os.environ.get("LATERALUS_WORKFLOW_SKILL_SCRIPTS_DIR")
PLANNING_STATE_TOOL_COMMAND = (
    f"python3 {shlex.quote(str(Path(SKILL_SCRIPTS_DIR) / 'planning_state.py'))}"
    if SKILL_SCRIPTS_DIR
    else "python3 .codex/workflow/scripts/planning_state.py"
)

PLANNING_PHASE_SEQUENCE = (
    "discuss",
    "discovery",
    "architecture_audit",
    "planning",
    "product_scope_audit",
    "skeptic_audit",
    "convergence",
    "approval_ready",
)
VALID_PLANNING_STATUSES = {
    *PLANNING_PHASE_SEQUENCE,
    "revising",
    "blocked",
}
DIRECT_COVERAGE_KEYWORDS = ("compatib", "consumer", "regression", "preserve")
DEFAULT_TOUCH_BUDGET = 8
DEFAULT_CREATE_BUDGET = 4


def load_planning_state(path: Path = DEFAULT_PLANNING_STATE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data = _normalize_planning_state_compat(data, path)
    validate_planning_state(data)
    return data


def save_planning_state(state: dict[str, Any], path: Path = DEFAULT_PLANNING_STATE_PATH) -> None:
    validate_planning_state(state)
    _write_json(path, state)


def load_discovery_dossier(path: Path = DEFAULT_DISCOVERY_DOSSIER_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("discovery dossier must be a JSON object")
    return payload


def clear_planning_state(path: Path = DEFAULT_PLANNING_STATE_PATH) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True


def build_planning_state(
    feature_request: str,
    *,
    approved_plan_path: str = ".codex/workflow/approved-plan.json",
    context_path: str = ".codex/workflow/context.json",
    discovery_dossier_path: str = ".codex/workflow/discovery_dossier.json",
    scope_contract_path: str = ".codex/workflow/scope_contract.json",
    architecture_constraints_path: str = ".codex/workflow/architecture_constraints.json",
    product_scope_audit_path: str = ".codex/workflow/product_scope_audit.json",
    skeptic_audit_path: str = ".codex/workflow/skeptic_audit.json",
    convergence_summary_path: str = ".codex/workflow/convergence_summary.json",
    planning_trace_path: str = ".codex/workflow/planning_trace.json",
    project_memory_path: str = "PROJECT.md",
    requirements_memory_path: str = "REQUIREMENTS.md",
    state_memory_path: str = "STATE.md",
) -> dict[str, Any]:
    feature_request = str(feature_request).strip()
    if not feature_request:
        raise ValueError("feature_request must be a non-empty string")

    return {
        "version": 1,
        "status": "discuss",
        "feature_request": feature_request,
        "approved_plan_path": approved_plan_path,
        "context_path": context_path,
        "discovery_dossier_path": discovery_dossier_path,
        "scope_contract_path": scope_contract_path,
        "architecture_constraints_path": architecture_constraints_path,
        "product_scope_audit_path": product_scope_audit_path,
        "skeptic_audit_path": skeptic_audit_path,
        "convergence_summary_path": convergence_summary_path,
        "planning_trace_path": planning_trace_path,
        "project_memory_path": project_memory_path,
        "requirements_memory_path": requirements_memory_path,
        "state_memory_path": state_memory_path,
        "phase_checkpoint": "discuss",
        "clarifying_question_limit": 3,
        "discovery_callback_limit": 2,
        "revision_count": 0,
        "latest_user_feedback": None,
    }


def validate_planning_state(state: dict[str, Any]) -> None:
    required_fields = {
        "version",
        "status",
        "feature_request",
        "approved_plan_path",
        "context_path",
        "discovery_dossier_path",
        "scope_contract_path",
        "architecture_constraints_path",
        "product_scope_audit_path",
        "skeptic_audit_path",
        "convergence_summary_path",
        "planning_trace_path",
        "project_memory_path",
        "requirements_memory_path",
        "state_memory_path",
        "phase_checkpoint",
        "clarifying_question_limit",
        "discovery_callback_limit",
        "revision_count",
        "latest_user_feedback",
    }
    missing = sorted(required_fields - state.keys())
    if missing:
        raise ValueError(f"planning state missing required fields: {', '.join(missing)}")

    if state["version"] != 1:
        raise ValueError("planning state version must be 1")
    if state["status"] not in VALID_PLANNING_STATUSES:
        raise ValueError(f"invalid planning status: {state['status']}")

    for field_name in (
        "feature_request",
        "approved_plan_path",
        "context_path",
        "discovery_dossier_path",
        "scope_contract_path",
        "architecture_constraints_path",
        "product_scope_audit_path",
        "skeptic_audit_path",
        "convergence_summary_path",
        "planning_trace_path",
        "project_memory_path",
        "requirements_memory_path",
        "state_memory_path",
    ):
        if not isinstance(state[field_name], str) or not state[field_name].strip():
            raise ValueError(f"{field_name} must be a non-empty string")

    if state["phase_checkpoint"] not in PLANNING_PHASE_SEQUENCE:
        raise ValueError(f"invalid phase_checkpoint: {state['phase_checkpoint']}")
    if state["status"] in PLANNING_PHASE_SEQUENCE and state["phase_checkpoint"] != state["status"]:
        raise ValueError("phase_checkpoint must match status while the plan is in an active planning phase")

    for field_name in ("clarifying_question_limit", "discovery_callback_limit", "revision_count"):
        if not isinstance(state[field_name], int) or state[field_name] < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")

    if state["clarifying_question_limit"] == 0:
        raise ValueError("clarifying_question_limit must be greater than zero")

    if not isinstance(state["latest_user_feedback"], (str, type(None))):
        raise ValueError("latest_user_feedback must be a string or null")


def _normalize_planning_state_compat(state: Any, path: Path) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ValueError("planning state must be a JSON object")

    normalized = dict(state)
    planning_root = path.resolve().parent
    repo_root = _planning_repo_root(planning_root)

    if normalized.get("status") == "intake":
        normalized["status"] = "discuss"

    normalized.setdefault("approved_plan_path", _relative_or_source(planning_root / "approved-plan.json"))
    normalized.setdefault("context_path", _relative_or_source(planning_root / "context.json"))
    normalized.setdefault(
        "discovery_dossier_path",
        _relative_or_source(planning_root / "discovery_dossier.json"),
    )
    normalized.setdefault("scope_contract_path", _relative_or_source(planning_root / "scope_contract.json"))
    normalized.setdefault(
        "architecture_constraints_path",
        _relative_or_source(planning_root / "architecture_constraints.json"),
    )
    normalized.setdefault(
        "product_scope_audit_path",
        _relative_or_source(planning_root / "product_scope_audit.json"),
    )
    normalized.setdefault(
        "skeptic_audit_path",
        _relative_or_source(planning_root / "skeptic_audit.json"),
    )
    normalized.setdefault(
        "convergence_summary_path",
        _relative_or_source(planning_root / "convergence_summary.json"),
    )
    normalized.setdefault("planning_trace_path", _relative_or_source(planning_root / "planning_trace.json"))
    normalized.setdefault("project_memory_path", _relative_or_source(repo_root / "PROJECT.md"))
    normalized.setdefault("requirements_memory_path", _relative_or_source(repo_root / "REQUIREMENTS.md"))
    normalized.setdefault("state_memory_path", _relative_or_source(repo_root / "STATE.md"))
    normalized.setdefault(
        "phase_checkpoint",
        normalized["status"] if normalized.get("status") in PLANNING_PHASE_SEQUENCE else "discuss",
    )

    return normalized


def initialize_planning_artifacts(state: dict[str, Any]) -> None:
    validate_planning_state(state)
    context_path = resolve_repo_path(state["context_path"])
    discovery_path = resolve_repo_path(state["discovery_dossier_path"])
    scope_contract_path = resolve_repo_path(state["scope_contract_path"])
    architecture_constraints_path = resolve_repo_path(state["architecture_constraints_path"])
    product_scope_audit_path = resolve_repo_path(state["product_scope_audit_path"])
    skeptic_audit_path = resolve_repo_path(state["skeptic_audit_path"])
    convergence_summary_path = resolve_repo_path(state["convergence_summary_path"])
    trace_path = resolve_repo_path(state["planning_trace_path"])
    project_memory_path = resolve_repo_path(state["project_memory_path"])
    requirements_memory_path = resolve_repo_path(state["requirements_memory_path"])
    state_memory_path = resolve_repo_path(state["state_memory_path"])

    context_payload = {
        "version": 1,
        "feature_request": state["feature_request"],
        "goal": "",
        "target_user": "",
        "desired_behavior": "",
        "good_outcomes": [],
        "bad_outcomes": [],
        "locked_decisions": [],
        "defaults_taken": [],
        "open_questions": [],
        "constraints": [],
        "success_criteria": [],
        "non_goals": [],
        "unresolved_risks": [],
    }
    discovery_payload = {
        "version": 1,
        "feature_request": state["feature_request"],
        "current": {
            "requirements": [],
            "anti_goals": [],
            "success_criteria": [],
            "entry_points": [],
            "blast_radius": [],
            "pattern_anchors": [],
            "verification_anchors": [],
            "open_questions": [],
            "complexity_events": [],
        },
        "supplements": [],
    }
    scope_contract_payload = {
        "version": 1,
        "feature_request": state["feature_request"],
        "must_have": [],
        "deferred": [],
        "non_goals": [],
        "success_criteria": [],
        "mvp_boundary": "",
        "defaults_taken": [],
    }
    architecture_constraints_payload = {
        "version": 1,
        "feature_request": state["feature_request"],
        "required_reuse": [],
        "approved_patterns": [],
        "forbidden_moves": [],
        "preserved_interfaces": [],
        "migration_constraints": [],
        "architecture_risks": [],
    }
    product_scope_audit_payload = {
        "version": 1,
        "feature_request": state["feature_request"],
        "included_scope": [],
        "deferred_scope": [],
        "defaults_taken": [],
        "unresolved_risks": [],
        "recommendation": "pending",
    }
    skeptic_audit_payload = {
        "version": 1,
        "feature_request": state["feature_request"],
        "objections": [],
        "unresolved_objections": [],
        "recommendation": "pending",
    }
    convergence_summary_payload = {
        "version": 1,
        "feature_request": state["feature_request"],
        "included_scope": [],
        "deferred_scope": [],
        "defaults_taken": [],
        "unresolved_risks": [],
        "approval_summary": "",
    }
    trace_payload = {
        "version": 1,
        "feature_request": state["feature_request"],
        "events": [
            {
                "sequence": 1,
                "event": "planning_started",
                "detail": "planning state initialized in discuss phase",
            }
        ],
    }

    _write_json(context_path, context_payload)
    _write_json(discovery_path, discovery_payload)
    _write_json(scope_contract_path, scope_contract_payload)
    _write_json(architecture_constraints_path, architecture_constraints_payload)
    _write_json(product_scope_audit_path, product_scope_audit_payload)
    _write_json(skeptic_audit_path, skeptic_audit_payload)
    _write_json(convergence_summary_path, convergence_summary_payload)
    _write_json(trace_path, trace_payload)

    if not project_memory_path.exists():
        _write_text(project_memory_path, _default_project_memory())
    if not requirements_memory_path.exists():
        _write_text(requirements_memory_path, _default_requirements_memory())
    if not state_memory_path.exists():
        _write_text(state_memory_path, _default_state_memory())


def append_trace_event(state: dict[str, Any], event: str, detail: str) -> None:
    trace_path = resolve_repo_path(state["planning_trace_path"])
    if trace_path.exists():
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    else:
        payload = {
            "version": 1,
            "feature_request": state["feature_request"],
            "events": [],
        }

    events = payload.setdefault("events", [])
    events.append(
        {
            "sequence": len(events) + 1,
            "event": event,
            "detail": detail,
        }
    )
    _write_json(trace_path, payload)


def apply_revision_feedback(state: dict[str, Any], feedback: str | None) -> dict[str, Any]:
    updated_state = dict(state)
    updated_state["status"] = "revising"
    updated_state["revision_count"] = updated_state["revision_count"] + 1
    updated_state["latest_user_feedback"] = str(feedback).strip() if feedback else None
    return updated_state


def set_planning_status(
    state: dict[str, Any],
    status: str,
    *,
    phase_checkpoint: str | None = None,
) -> dict[str, Any]:
    validate_planning_state(state)
    if status not in VALID_PLANNING_STATUSES:
        raise ValueError(f"invalid planning status: {status}")

    updated_state = dict(state)
    updated_state["status"] = status
    if status in PLANNING_PHASE_SEQUENCE:
        updated_state["phase_checkpoint"] = status
    elif phase_checkpoint is not None:
        if phase_checkpoint not in PLANNING_PHASE_SEQUENCE:
            raise ValueError(f"invalid phase_checkpoint: {phase_checkpoint}")
        updated_state["phase_checkpoint"] = phase_checkpoint
    validate_planning_state(updated_state)
    return updated_state


def planning_phase_checkpoint(state: dict[str, Any]) -> str:
    validate_planning_state(state)
    if state["status"] in PLANNING_PHASE_SEQUENCE:
        return state["status"]
    return state["phase_checkpoint"]


def validate_phase_outputs(state: dict[str, Any], *, phase: str | None = None) -> list[str]:
    validate_planning_state(state)
    phase_name = phase or planning_phase_checkpoint(state)
    if phase_name not in PLANNING_PHASE_SEQUENCE:
        raise ValueError(f"unsupported planning phase: {phase_name}")

    if phase_name == "discuss":
        return _validate_discuss_phase(state)
    if phase_name == "discovery":
        return _validate_discovery_phase(state)
    if phase_name == "architecture_audit":
        return _validate_architecture_audit_phase(state)
    if phase_name == "planning":
        return _validate_planning_phase(state)
    if phase_name == "product_scope_audit":
        return _validate_product_scope_audit_phase(state)
    if phase_name == "skeptic_audit":
        return _validate_skeptic_audit_phase(state)
    if phase_name == "convergence":
        return _validate_convergence_phase(state)
    if phase_name == "approval_ready":
        return _validate_approval_ready_phase(state)
    raise ValueError(f"unsupported planning phase: {phase_name}")


def advance_planning_phase(state: dict[str, Any], *, target_status: str | None = None) -> dict[str, Any]:
    validate_planning_state(state)
    current_phase = planning_phase_checkpoint(state)
    current_index = PLANNING_PHASE_SEQUENCE.index(current_phase)

    if state["status"] == "approval_ready":
        raise ValueError("planning state is already approval_ready")

    if target_status is None:
        if state["status"] in {"blocked", "revising"}:
            raise ValueError("blocked or revising planning state requires an explicit target_status")
        target_status = PLANNING_PHASE_SEQUENCE[current_index + 1]

    if target_status not in PLANNING_PHASE_SEQUENCE:
        raise ValueError(f"target_status must be a planning phase: {target_status}")

    target_index = PLANNING_PHASE_SEQUENCE.index(target_status)
    if state["status"] in {"blocked", "revising"}:
        allowed_indexes = {current_index, min(current_index + 1, len(PLANNING_PHASE_SEQUENCE) - 1)}
        if target_index not in allowed_indexes:
            raise ValueError(
                f"{state['status']} planning state can only return to `{current_phase}` or advance to "
                f"`{PLANNING_PHASE_SEQUENCE[min(current_index + 1, len(PLANNING_PHASE_SEQUENCE) - 1)]}`"
            )
        if target_status == current_phase:
            return set_planning_status(state, target_status)
    elif target_index != current_index + 1:
        raise ValueError(
            f"invalid planning phase transition: `{state['status']}` -> `{target_status}`"
        )

    issues = validate_phase_outputs(state, phase=current_phase)
    if issues:
        joined = "\n- ".join(issues)
        raise ValueError(f"cannot advance planning phase from `{current_phase}`:\n- {joined}")

    if target_status == "approval_ready":
        target_issues = validate_phase_outputs(state, phase="approval_ready")
        if target_issues:
            joined = "\n- ".join(target_issues)
            raise ValueError("cannot advance planning phase into `approval_ready`:\n- " + joined)

    return set_planning_status(state, target_status)


def approve_planning(
    state: dict[str, Any],
    *,
    planning_state_path: Path = DEFAULT_PLANNING_STATE_PATH,
    execution_state_path: Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    validate_planning_state(state)
    if state["status"] != "approval_ready":
        raise ValueError(f"planning state is not approval_ready: {state['status']}")

    audit_issues = audit_planning_artifacts(state)
    if audit_issues:
        joined = "\n- ".join(audit_issues)
        raise ValueError(f"approved plan failed planning audit:\n- {joined}")

    approved_plan_path = resolve_repo_path(state["approved_plan_path"])
    plan_spec = load_plan_spec(approved_plan_path)
    execution_state = build_state_from_plan_spec(
        plan_spec,
        plan_path=_relative_or_source(approved_plan_path),
    )
    save_state(execution_state, execution_state_path)
    append_trace_event(state, "plan_approved", "approved plan ingested into execution state")
    clear_planning_state(planning_state_path)
    return execution_state


def planning_activation_prompt(state: dict[str, Any], *, revision_mode: bool = False) -> str:
    validate_planning_state(state)
    phase_name = planning_phase_checkpoint(state)
    intro = "Revise the active plan request." if revision_mode else "Start the workflow planning phase."
    revision_note = ""
    if state["latest_user_feedback"]:
        revision_note = f"Latest revision request:\n- {state['latest_user_feedback']}\n\n"

    phase_header = _planning_phase_header(state, phase_name)
    phase_contract = _planning_phase_contract(state, phase_name=phase_name)
    status_note = ""
    if state["status"] == "blocked":
        status_note = (
            "This planning session is blocked. Repair the required artifacts for the checkpointed phase before "
            "advancing.\n\n"
        )
    elif state["status"] == "revising":
        status_note = (
            "This planning session is in revision mode. Update the relevant artifacts, then either re-enter the "
            f"`{phase_name}` phase or advance once its outputs validate cleanly.\n\n"
        )

    return (
        f"{intro}\n\n"
        f"{phase_header}\n\n"
        f"{revision_note}"
        f"{status_note}"
        "Plan-phase rules:\n"
        "- Do not write implementation code.\n"
        "- Treat `$workflow` as the canonical entrypoint; the legacy `/workflow` hook is compatibility-only.\n"
        "- `$workflow <feature request>` starts with discuss automatically; do not skip discuss.\n"
        "- Root `AGENTS.md` must be read before scoped discovery, then load only the relevant `AGENTS.md` files.\n"
        "- Ask at most 3 clarification questions, only when ambiguity would materially change architecture, scope, or verification.\n"
        "- Distinguish facts from assumptions explicitly.\n"
        "- Do not let a single planner own the final truth; convergence must merge discuss, discovery, architecture, full-plan coverage, MVP pressure, and skeptic findings.\n"
        "- Planning may update `PROJECT.md` only when product intent or durable constraints change.\n"
        "- Planning may update `REQUIREMENTS.md` only when scope, backlog, or milestone commitments change.\n"
        "- Execution and ship own `STATE.md`; planning should read it for active initiative and risk context, not silently rewrite delivery state.\n"
        "- Feature plans must stay aligned with repo memory and must not re-introduce items listed as deferred scope.\n"
        "- Each step in the approved plan must include justification, files_read_first, interfaces_to_preserve, avoid_touching, and verification_targets.\n"
        "- Each step should declare wave, file ownership, dependency edges, and rollback/watchpoint notes when the blast radius warrants them.\n"
        "- Any step that claims compatibility or verification across discovered entry points must include the "
        "direct consumer tests implied by that blast radius, not just a broad end-to-end check.\n"
        "- Prefer the smallest sufficient design and reject speculative abstractions or generic frameworks unless the milestone truly needs them.\n"
        f"- Before approval readiness, run `{PLANNING_STATE_TOOL_COMMAND} audit-plan` and fix every reported issue.\n"
        f"{phase_contract}"
        "- Present only the rendered plan summary to the user and ask for explicit approval.\n"
        f"- If the plan is blocked, run `{PLANNING_STATE_TOOL_COMMAND} set-status blocked` and explain the "
        "blocker."
    )


def render_planning_status(state: dict[str, Any]) -> str:
    validate_planning_state(state)
    phase_name = planning_phase_checkpoint(state)
    approved_exists = resolve_repo_path(state["approved_plan_path"]).exists()
    context_exists = resolve_repo_path(state["context_path"]).exists()
    discovery_exists = resolve_repo_path(state["discovery_dossier_path"]).exists()
    scope_exists = resolve_repo_path(state["scope_contract_path"]).exists()
    architecture_exists = resolve_repo_path(state["architecture_constraints_path"]).exists()
    product_scope_audit_exists = resolve_repo_path(state["product_scope_audit_path"]).exists()
    skeptic_audit_exists = resolve_repo_path(state["skeptic_audit_path"]).exists()
    convergence_exists = resolve_repo_path(state["convergence_summary_path"]).exists()
    trace_exists = resolve_repo_path(state["planning_trace_path"]).exists()
    project_memory_exists = resolve_repo_path(state["project_memory_path"]).exists()
    requirements_memory_exists = resolve_repo_path(state["requirements_memory_path"]).exists()
    state_memory_exists = resolve_repo_path(state["state_memory_path"]).exists()
    feedback = state["latest_user_feedback"] or "none"

    return (
        f"Plan status: `{state['status']}`\n"
        f"Phase checkpoint: `{phase_name}`\n"
        f"Feature request: {state['feature_request']}\n"
        f"Approved plan artifact: `{state['approved_plan_path']}` ({_present(approved_exists)})\n"
        f"Context artifact: `{state['context_path']}` ({_present(context_exists)})\n"
        f"Discovery dossier: `{state['discovery_dossier_path']}` ({_present(discovery_exists)})\n"
        f"Scope contract: `{state['scope_contract_path']}` ({_present(scope_exists)})\n"
        f"Architecture constraints: `{state['architecture_constraints_path']}` ({_present(architecture_exists)})\n"
        f"Product scope audit: `{state['product_scope_audit_path']}` ({_present(product_scope_audit_exists)})\n"
        f"Skeptic audit: `{state['skeptic_audit_path']}` ({_present(skeptic_audit_exists)})\n"
        f"Convergence summary: `{state['convergence_summary_path']}` ({_present(convergence_exists)})\n"
        f"Planning trace: `{state['planning_trace_path']}` ({_present(trace_exists)})\n"
        f"Project memory: `{state['project_memory_path']}` ({_present(project_memory_exists)})\n"
        f"Requirements memory: `{state['requirements_memory_path']}` ({_present(requirements_memory_exists)})\n"
        f"Project state memory: `{state['state_memory_path']}` ({_present(state_memory_exists)})\n"
        f"Revision count: {state['revision_count']}\n"
        f"Latest user feedback: {feedback}"
    )


def execution_status_summary(state: dict[str, Any]) -> str:
    step = next(step for step in state["steps"] if step["id"] == state["current_step_id"])
    return (
        f"Execution workflow: `{state['workflow_name']}`\n"
        f"Workflow status: `{state['workflow_status']}`\n"
        f"Current step: `{step['id']}` - {step['title']}\n"
        f"Current step status: `{step['status']}`\n"
        f"Plan source: `{state['plan_path']}`"
    )


def audit_planning_artifacts(state: dict[str, Any]) -> list[str]:
    validate_planning_state(state)
    approved_plan_path = resolve_repo_path(state["approved_plan_path"])
    context_path = resolve_repo_path(state["context_path"])
    discovery_path = resolve_repo_path(state["discovery_dossier_path"])
    scope_contract_path = resolve_repo_path(state["scope_contract_path"])
    architecture_constraints_path = resolve_repo_path(state["architecture_constraints_path"])
    project_memory_path = resolve_repo_path(state["project_memory_path"])
    requirements_memory_path = resolve_repo_path(state["requirements_memory_path"])
    state_memory_path = resolve_repo_path(state["state_memory_path"])

    context = _load_required_artifact(context_path, "context artifact")
    discovery = load_discovery_dossier(discovery_path)
    scope_contract = _load_required_artifact(scope_contract_path, "scope contract")
    architecture_constraints = _load_required_artifact(
        architecture_constraints_path,
        "architecture constraints",
    )
    if discovery is None:
        raise ValueError(f"discovery dossier not found: {discovery_path}")
    project_memory = _load_memory_document(project_memory_path, "project memory")
    requirements_memory = _load_memory_document(requirements_memory_path, "requirements memory")
    state_memory = _load_memory_document(state_memory_path, "state memory")

    plan_spec = load_plan_spec(approved_plan_path)
    return audit_plan_bundle(
        plan_spec,
        context=context,
        discovery=discovery,
        scope_contract=scope_contract,
        architecture_constraints=architecture_constraints,
        project_memory=project_memory,
        requirements_memory=requirements_memory,
        state_memory=state_memory,
    )


def audit_plan_bundle(
    plan_spec: dict[str, Any],
    *,
    context: dict[str, Any],
    discovery: dict[str, Any],
    scope_contract: dict[str, Any],
    architecture_constraints: dict[str, Any],
    project_memory: dict[str, list[str]] | None = None,
    requirements_memory: dict[str, list[str]] | None = None,
    state_memory: dict[str, list[str]] | None = None,
) -> list[str]:
    issues = audit_plan_against_discovery(plan_spec, discovery)
    issues.extend(_audit_context_artifact(context))
    issues.extend(_audit_scope_contract(scope_contract))
    issues.extend(_audit_architecture_constraints(architecture_constraints))
    issues.extend(
        _audit_project_memory(
            plan_spec,
            project_memory=project_memory,
            requirements_memory=requirements_memory,
            state_memory=state_memory,
        )
    )
    issues.extend(
        _audit_plan_contract(
            plan_spec,
            discovery=discovery,
            scope_contract=scope_contract,
            architecture_constraints=architecture_constraints,
        )
    )
    return issues


def audit_plan_against_discovery(plan_spec: dict[str, Any], discovery: dict[str, Any]) -> list[str]:
    current = discovery.get("current")
    if not isinstance(current, dict):
        raise ValueError("discovery dossier missing current section")

    entry_points = _ensure_discovery_string_list(current.get("entry_points", []), "current.entry_points")
    if not entry_points:
        return []

    requirements_by_id = {
        str(requirement["id"]): requirement for requirement in plan_spec.get("requirements", []) if isinstance(requirement, dict)
    }

    issues: list[str] = []
    for step in plan_spec.get("steps", []):
        if not isinstance(step, dict):
            continue
        impacted_entry_points = _impacted_entry_points_for_step(step, entry_points)
        if not impacted_entry_points or not _step_requires_direct_coverage(step, requirements_by_id):
            continue

        required_targets = _direct_verification_targets_for_entry_points(impacted_entry_points)
        if not required_targets:
            continue

        verify_cmds = [
            command
            for command in step.get("verify_cmds", [])
            if isinstance(command, str) and command.strip()
        ]
        missing_targets = [
            target for target in required_targets if not any(target in command for command in verify_cmds)
        ]
        if missing_targets:
            issues.append(
                f"step {step.get('id', '<unknown>')} is missing direct verification for discovered consumers: "
                + ", ".join(missing_targets)
            )

    return issues


def _audit_context_artifact(context: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not _artifact_non_empty_string(context.get("goal")):
        issues.append("context artifact is missing a goal")
    if not _artifact_non_empty_string(context.get("desired_behavior")):
        issues.append("context artifact is missing desired_behavior")
    if not _artifact_string_list(context.get("success_criteria")):
        issues.append("context artifact must include at least one success_criteria entry")
    if context.get("open_questions"):
        issues.append("context artifact still has unresolved open_questions")
    return issues


def _audit_scope_contract(scope_contract: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not _artifact_string_list(scope_contract.get("must_have")):
        issues.append("scope contract must include at least one must_have item")
    if not _artifact_non_empty_string(scope_contract.get("mvp_boundary")):
        issues.append("scope contract is missing mvp_boundary")
    if not _artifact_string_list(scope_contract.get("success_criteria")):
        issues.append("scope contract must include at least one success_criteria entry")
    return issues


def _audit_architecture_constraints(architecture_constraints: dict[str, Any]) -> list[str]:
    if any(
        _artifact_string_list(architecture_constraints.get(field_name))
        for field_name in (
            "required_reuse",
            "approved_patterns",
            "forbidden_moves",
            "preserved_interfaces",
            "migration_constraints",
        )
    ):
        return []
    return [
        "architecture constraints must capture at least one required reuse, approved pattern, forbidden move, preserved interface, or migration constraint"
    ]


def _audit_project_memory(
    plan_spec: dict[str, Any],
    *,
    project_memory: dict[str, list[str]] | None,
    requirements_memory: dict[str, list[str]] | None,
    state_memory: dict[str, list[str]] | None,
) -> list[str]:
    issues: list[str] = []
    plan_text = _plan_text(plan_spec)

    if project_memory is not None:
        durable_constraints = project_memory.get("durable constraints", [])
        missing_constraints = [
            item for item in durable_constraints if item.lower() not in plan_text
        ]
        if missing_constraints:
            issues.append(
                "approved plan does not acknowledge durable constraints from PROJECT.md: "
                + ", ".join(missing_constraints)
            )

    if requirements_memory is not None:
        deferred_scope = requirements_memory.get("deferred scope", [])
        leaked = [item for item in deferred_scope if item.lower() in plan_text]
        if leaked:
            issues.append(
                "approved plan still includes items marked deferred in REQUIREMENTS.md: "
                + ", ".join(leaked)
            )

    if state_memory is not None:
        active_initiative = state_memory.get("active initiative", [])
        if active_initiative and not any(item.lower() in plan_text for item in active_initiative):
            issues.append(
                "approved plan does not reference the active initiative from STATE.md: "
                + ", ".join(active_initiative)
            )

    return issues


def _audit_plan_contract(
    plan_spec: dict[str, Any],
    *,
    discovery: dict[str, Any],
    scope_contract: dict[str, Any],
    architecture_constraints: dict[str, Any],
) -> list[str]:
    discovery_current = discovery.get("current", {})
    known_entry_points = set(_artifact_string_list(discovery_current.get("entry_points")))
    known_entry_points.update(_artifact_string_list(discovery_current.get("pattern_anchors")))
    preserved_interfaces = set(_artifact_string_list(architecture_constraints.get("preserved_interfaces")))
    deferred_items = _artifact_string_list(scope_contract.get("deferred"))

    issues: list[str] = []
    seen_preserved_interfaces: set[str] = set()
    steps_by_id: dict[str, dict[str, Any]] = {}
    step_order: dict[str, int] = {}
    step_waves: dict[str, int] = {}
    step_dependencies: dict[str, list[str]] = {}
    wave_ownership: dict[int, list[tuple[str, list[str]]]] = {}

    for index, step in enumerate(plan_spec.get("steps", []), start=1):
        if not isinstance(step, dict):
            continue

        step_id = str(step.get("id") or f"step-{index}")
        justification = str(step.get("justification") or "").strip()
        files_read_first = _artifact_string_list(step.get("files_read_first"))
        interfaces_to_preserve = _artifact_string_list(step.get("interfaces_to_preserve"))
        avoid_touching = _artifact_string_list(step.get("avoid_touching"))
        verification_targets = _artifact_string_list(step.get("verification_targets"))
        risk_flags = _artifact_string_list(step.get("risk_flags"))
        blast_radius = _artifact_string_list(step.get("blast_radius"))
        depends_on = _artifact_string_list(step.get("depends_on"))
        file_ownership = _artifact_string_list(step.get("file_ownership"))
        rollback_notes = _artifact_string_list(step.get("rollback_notes"))
        operational_watchpoints = _artifact_string_list(step.get("operational_watchpoints"))
        done_when = _artifact_string_list(step.get("done_when"))
        verify_cmds = _artifact_string_list(step.get("verify_cmds"))
        context_paths = set(_artifact_string_list(step.get("context")))
        planned_updates = _artifact_string_list(step.get("planned_updates"))
        planned_creates = _artifact_string_list(step.get("planned_creates"))
        wave = step.get("wave")

        if not justification:
            issues.append(f"step {step_id} is missing justification")
        if not files_read_first:
            issues.append(f"step {step_id} is missing files_read_first")
        if not interfaces_to_preserve:
            issues.append(f"step {step_id} is missing interfaces_to_preserve")
        if not avoid_touching:
            issues.append(f"step {step_id} is missing avoid_touching")
        if not verification_targets:
            issues.append(f"step {step_id} is missing verification_targets")
        if not file_ownership:
            issues.append(f"step {step_id} is missing file_ownership")
        if wave is None:
            issues.append(f"step {step_id} is missing wave")
        elif not isinstance(wave, int) or wave < 1:
            issues.append(f"step {step_id} wave must be a positive integer")
        if risk_flags and not rollback_notes:
            issues.append(f"step {step_id} is risky but is missing rollback_notes")
        if blast_radius and not operational_watchpoints:
            issues.append(f"step {step_id} has blast radius but is missing operational_watchpoints")

        for target in files_read_first:
            if target not in context_paths:
                issues.append(f"step {step_id} files_read_first entry is outside the step context: {target}")

        for target in verification_targets:
            if not any(target in command for command in verify_cmds):
                issues.append(f"step {step_id} verification target is not exercised by verify_cmds: {target}")

        for path in planned_updates:
            if path in context_paths or path in known_entry_points or path.startswith("tests/"):
                continue
            issues.append(
                f"step {step_id} updates a file that is not justified by step context or discovery blast radius: {path}"
            )

        for path in planned_updates + planned_creates:
            if file_ownership and not any(_repo_path_covers(owner, path) for owner in file_ownership):
                issues.append(f"step {step_id} touches `{path}` outside file_ownership")

        seen_preserved_interfaces.update(interfaces_to_preserve)
        steps_by_id[step_id] = step
        step_order[step_id] = index
        if isinstance(wave, int) and wave > 0:
            step_waves[step_id] = wave
            wave_ownership.setdefault(wave, []).append((step_id, file_ownership))
        step_dependencies[step_id] = depends_on

    missing_interfaces = sorted(preserved_interfaces - seen_preserved_interfaces)
    if missing_interfaces:
        issues.append(
            "approved plan does not acknowledge preserved interfaces from architecture constraints: "
            + ", ".join(missing_interfaces)
        )

    issues.extend(
        _audit_step_dependencies(
            steps_by_id=steps_by_id,
            step_order=step_order,
            step_waves=step_waves,
            step_dependencies=step_dependencies,
        )
    )
    issues.extend(_audit_parallel_file_ownership(wave_ownership))

    if deferred_items:
        plan_text = _plan_text(plan_spec)
        leaked = sorted(item for item in deferred_items if item.lower() in plan_text)
        if leaked:
            issues.append(
                "approved plan still includes items marked deferred in scope contract: " + ", ".join(leaked)
            )

    return issues


def evaluate_plan_spec(
    plan_spec: dict[str, Any],
    *,
    discovery: dict[str, Any] | None = None,
    touch_budget: int = DEFAULT_TOUCH_BUDGET,
    create_budget: int = DEFAULT_CREATE_BUDGET,
) -> dict[str, Any]:
    if touch_budget <= 0:
        raise ValueError("touch_budget must be greater than zero")
    if create_budget < 0:
        raise ValueError("create_budget must be non-negative")

    plan_spec = dict(plan_spec)
    validate_plan_spec(plan_spec)

    steps = [step for step in plan_spec.get("steps", []) if isinstance(step, dict)]
    requirements = [requirement for requirement in plan_spec.get("requirements", []) if isinstance(requirement, dict)]
    requirement_kinds = {
        "behavior": 0,
        "constraint": 0,
        "verification": 0,
        "other": 0,
    }
    for requirement in requirements:
        kind = str(requirement.get("kind") or "other").strip().lower()
        if kind not in requirement_kinds:
            kind = "other"
        requirement_kinds[kind] += 1

    unique_context_paths: set[str] = set()
    unique_update_paths: set[str] = set()
    unique_create_paths: set[str] = set()
    unique_verify_targets: set[str] = set()
    steps_exceeding_touch_budget: list[str] = []
    steps_exceeding_create_budget: list[str] = []
    steps_missing_constraints: list[str] = []
    steps_missing_justification: list[str] = []
    steps_missing_files_read_first: list[str] = []
    steps_missing_interfaces_to_preserve: list[str] = []
    steps_missing_avoid_touching: list[str] = []
    steps_missing_verification_targets: list[str] = []
    steps_missing_wave: list[str] = []
    steps_missing_file_ownership: list[str] = []
    risky_steps_missing_rollback_notes: list[str] = []
    blast_radius_steps_missing_watchpoints: list[str] = []
    steps_missing_done_detail: list[str] = []
    step_summaries: list[dict[str, Any]] = []
    step_order: dict[str, int] = {}
    step_waves: dict[str, int] = {}
    step_dependencies: dict[str, list[str]] = {}
    wave_ownership: dict[int, list[tuple[str, list[str]]]] = {}

    total_constraints = 0
    total_done_when = 0
    total_verify_cmds = 0
    total_touched_files = 0
    max_touched_files = 0

    for index, step in enumerate(steps, start=1):
        step_id = str(step.get("id") or f"step-{index}")
        context_paths = _ensure_string_list(step.get("context", []), field_name=f"context for {step_id}")
        update_paths = _ensure_string_list(step.get("planned_updates", []), field_name=f"planned_updates for {step_id}")
        create_paths = _ensure_string_list(step.get("planned_creates", []), field_name=f"planned_creates for {step_id}")
        constraints = _ensure_string_list(step.get("constraints", []), field_name=f"constraints for {step_id}")
        done_when = _ensure_string_list(step.get("done_when", []), field_name=f"done_when for {step_id}")
        verify_cmds = _ensure_string_list(step.get("verify_cmds", []), field_name=f"verify_cmds for {step_id}")
        files_read_first = _ensure_string_list(
            step.get("files_read_first", []),
            field_name=f"files_read_first for {step_id}",
        )
        interfaces_to_preserve = _ensure_string_list(
            step.get("interfaces_to_preserve", []),
            field_name=f"interfaces_to_preserve for {step_id}",
        )
        avoid_touching = _ensure_string_list(
            step.get("avoid_touching", []),
            field_name=f"avoid_touching for {step_id}",
        )
        verification_targets = _ensure_string_list(
            step.get("verification_targets", []),
            field_name=f"verification_targets for {step_id}",
        )
        depends_on = _ensure_string_list(step.get("depends_on", []), field_name=f"depends_on for {step_id}")
        file_ownership = _ensure_string_list(
            step.get("file_ownership", []),
            field_name=f"file_ownership for {step_id}",
        )
        rollback_notes = _ensure_string_list(
            step.get("rollback_notes", []),
            field_name=f"rollback_notes for {step_id}",
        )
        operational_watchpoints = _ensure_string_list(
            step.get("operational_watchpoints", []),
            field_name=f"operational_watchpoints for {step_id}",
        )
        risk_flags = _ensure_string_list(step.get("risk_flags", []), field_name=f"risk_flags for {step_id}")
        blast_radius = _ensure_string_list(step.get("blast_radius", []), field_name=f"blast_radius for {step_id}")
        wave = step.get("wave")

        unique_context_paths.update(context_paths)
        unique_update_paths.update(update_paths)
        unique_create_paths.update(create_paths)

        touched_paths = sorted(dict.fromkeys(update_paths + create_paths))
        touched_count = len(touched_paths)
        create_count = len(create_paths)
        constraints_count = len(constraints)
        done_when_count = len(done_when)
        verify_cmds_count = len(verify_cmds)
        verify_targets = _extract_verify_targets(verify_cmds)
        unique_verify_targets.update(verify_targets)

        total_constraints += constraints_count
        total_done_when += done_when_count
        total_verify_cmds += verify_cmds_count
        total_touched_files += touched_count
        max_touched_files = max(max_touched_files, touched_count)

        if touched_count > touch_budget:
            steps_exceeding_touch_budget.append(step_id)
        if create_count > create_budget:
            steps_exceeding_create_budget.append(step_id)
        if constraints_count == 0:
            steps_missing_constraints.append(step_id)
        if not str(step.get("justification") or "").strip():
            steps_missing_justification.append(step_id)
        if not files_read_first:
            steps_missing_files_read_first.append(step_id)
        if not interfaces_to_preserve:
            steps_missing_interfaces_to_preserve.append(step_id)
        if not avoid_touching:
            steps_missing_avoid_touching.append(step_id)
        if not verification_targets:
            steps_missing_verification_targets.append(step_id)
        if wave is None:
            steps_missing_wave.append(step_id)
        elif isinstance(wave, int) and wave > 0:
            step_waves[step_id] = wave
            wave_ownership.setdefault(wave, []).append((step_id, file_ownership))
        if not file_ownership:
            steps_missing_file_ownership.append(step_id)
        if risk_flags and not rollback_notes:
            risky_steps_missing_rollback_notes.append(step_id)
        if blast_radius and not operational_watchpoints:
            blast_radius_steps_missing_watchpoints.append(step_id)
        if done_when_count < 2:
            steps_missing_done_detail.append(step_id)

        step_order[step_id] = index
        step_dependencies[step_id] = depends_on

        step_summaries.append(
            {
                "id": step_id,
                "requirement_count": len(_ensure_string_list(step.get("requirement_ids", []), field_name=f"requirement_ids for {step_id}")),
                "context_count": len(context_paths),
                "update_count": len(update_paths),
                "create_count": create_count,
                "touched_count": touched_count,
                "constraints_count": constraints_count,
                "done_when_count": done_when_count,
                "verify_cmds_count": verify_cmds_count,
                "files_read_first_count": len(files_read_first),
                "interfaces_to_preserve_count": len(interfaces_to_preserve),
                "avoid_touching_count": len(avoid_touching),
                "verification_targets_count": len(verification_targets),
                "depends_on_count": len(depends_on),
                "file_ownership_count": len(file_ownership),
                "rollback_notes_count": len(rollback_notes),
                "operational_watchpoints_count": len(operational_watchpoints),
                "verify_targets": verify_targets,
            }
        )

    discovery_issues = audit_plan_against_discovery(plan_spec, discovery) if discovery is not None else []
    dependency_issues = _audit_step_dependencies(
        steps_by_id={step_id: step for step_id, step in ((str(step.get("id") or f"step-{index}"), step) for index, step in enumerate(steps, start=1))},
        step_order=step_order,
        step_waves=step_waves,
        step_dependencies=step_dependencies,
    )
    ownership_issues = _audit_parallel_file_ownership(wave_ownership)
    step_count = len(steps)
    divisor = step_count or 1

    warnings: list[str] = []
    for step_id in steps_exceeding_touch_budget:
        warnings.append(f"{step_id} exceeds the touched-file budget of {touch_budget}")
    for step_id in steps_exceeding_create_budget:
        warnings.append(f"{step_id} exceeds the created-file budget of {create_budget}")
    for step_id in steps_missing_constraints:
        warnings.append(f"{step_id} is missing explicit constraints")
    for step_id in steps_missing_justification:
        warnings.append(f"{step_id} is missing a step justification")
    for step_id in steps_missing_files_read_first:
        warnings.append(f"{step_id} is missing files_read_first")
    for step_id in steps_missing_interfaces_to_preserve:
        warnings.append(f"{step_id} is missing interfaces_to_preserve")
    for step_id in steps_missing_avoid_touching:
        warnings.append(f"{step_id} is missing avoid_touching")
    for step_id in steps_missing_verification_targets:
        warnings.append(f"{step_id} is missing verification_targets")
    for step_id in steps_missing_wave:
        warnings.append(f"{step_id} is missing wave")
    for step_id in steps_missing_file_ownership:
        warnings.append(f"{step_id} is missing file_ownership")
    for step_id in risky_steps_missing_rollback_notes:
        warnings.append(f"{step_id} is risky but is missing rollback_notes")
    for step_id in blast_radius_steps_missing_watchpoints:
        warnings.append(f"{step_id} has blast radius but is missing operational_watchpoints")
    for step_id in steps_missing_done_detail:
        warnings.append(f"{step_id} has only one done_when outcome; add more concrete completion detail")
    for issue in discovery_issues:
        warnings.append(issue)
    for issue in dependency_issues:
        warnings.append(issue)
    for issue in ownership_issues:
        warnings.append(issue)

    return {
        "workflow_name": plan_spec["workflow_name"],
        "summary": plan_spec["summary"],
        "metrics": {
            "requirements_count": len(requirements),
            "requirement_kind_counts": requirement_kinds,
            "steps_count": step_count,
            "assumptions_count": len(_ensure_string_list(plan_spec.get("assumptions", []), field_name="assumptions")),
            "open_questions_count": len(_ensure_string_list(plan_spec.get("open_questions", []), field_name="open_questions")),
            "out_of_scope_count": len(_ensure_string_list(plan_spec.get("out_of_scope", []), field_name="out_of_scope")),
            "unique_context_paths_count": len(unique_context_paths),
            "unique_update_paths_count": len(unique_update_paths),
            "unique_create_paths_count": len(unique_create_paths),
            "unique_touched_paths_count": len(unique_update_paths | unique_create_paths),
            "unique_verify_targets_count": len(unique_verify_targets),
            "total_constraints_count": total_constraints,
            "total_done_when_count": total_done_when,
            "total_verify_cmds_count": total_verify_cmds,
            "avg_constraints_per_step": round(total_constraints / divisor, 2),
            "avg_done_when_per_step": round(total_done_when / divisor, 2),
            "avg_verify_cmds_per_step": round(total_verify_cmds / divisor, 2),
            "avg_touched_files_per_step": round(total_touched_files / divisor, 2),
            "max_touched_files_per_step": max_touched_files,
            "steps_exceeding_touch_budget_count": len(steps_exceeding_touch_budget),
            "steps_exceeding_create_budget_count": len(steps_exceeding_create_budget),
            "steps_missing_constraints_count": len(steps_missing_constraints),
            "steps_missing_justification_count": len(steps_missing_justification),
            "steps_missing_files_read_first_count": len(steps_missing_files_read_first),
            "steps_missing_interfaces_to_preserve_count": len(steps_missing_interfaces_to_preserve),
            "steps_missing_avoid_touching_count": len(steps_missing_avoid_touching),
            "steps_missing_verification_targets_count": len(steps_missing_verification_targets),
            "steps_missing_wave_count": len(steps_missing_wave),
            "steps_missing_file_ownership_count": len(steps_missing_file_ownership),
            "risky_steps_missing_rollback_notes_count": len(risky_steps_missing_rollback_notes),
            "blast_radius_steps_missing_watchpoints_count": len(blast_radius_steps_missing_watchpoints),
            "steps_with_thin_done_when_count": len(steps_missing_done_detail),
            "direct_consumer_audit_issue_count": len(discovery_issues),
            "dependency_audit_issue_count": len(dependency_issues),
            "parallel_ownership_issue_count": len(ownership_issues),
        },
        "warnings": warnings,
        "step_summaries": step_summaries,
        "sets": {
            "context_paths": sorted(unique_context_paths),
            "update_paths": sorted(unique_update_paths),
            "create_paths": sorted(unique_create_paths),
            "touched_paths": sorted(unique_update_paths | unique_create_paths),
            "verify_targets": sorted(unique_verify_targets),
        },
    }


def compare_plan_specs(
    baseline_plan_spec: dict[str, Any],
    candidate_plan_spec: dict[str, Any],
    *,
    baseline_discovery: dict[str, Any] | None = None,
    candidate_discovery: dict[str, Any] | None = None,
    touch_budget: int = DEFAULT_TOUCH_BUDGET,
    create_budget: int = DEFAULT_CREATE_BUDGET,
) -> dict[str, Any]:
    baseline = evaluate_plan_spec(
        baseline_plan_spec,
        discovery=baseline_discovery,
        touch_budget=touch_budget,
        create_budget=create_budget,
    )
    candidate = evaluate_plan_spec(
        candidate_plan_spec,
        discovery=candidate_discovery,
        touch_budget=touch_budget,
        create_budget=create_budget,
    )

    improved: list[str] = []
    regressed: list[str] = []
    unchanged: list[str] = []

    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="direct_consumer_audit_issue_count",
        label="direct consumer verification coverage",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="unique_verify_targets_count",
        label="verification target breadth",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=False,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="avg_done_when_per_step",
        label="completion detail per step",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=False,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="avg_touched_files_per_step",
        label="step size discipline",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="max_touched_files_per_step",
        label="largest step blast radius",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="steps_exceeding_touch_budget_count",
        label="oversized step count",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="steps_missing_constraints_count",
        label="constraint completeness",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="steps_missing_justification_count",
        label="step justification coverage",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="steps_missing_files_read_first_count",
        label="read-first handoff coverage",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="steps_missing_interfaces_to_preserve_count",
        label="preserved interface coverage",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="steps_missing_avoid_touching_count",
        label="no-touch guardrails",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="steps_missing_verification_targets_count",
        label="verification target mapping",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="steps_missing_wave_count",
        label="wave coverage",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="steps_missing_file_ownership_count",
        label="file ownership coverage",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="risky_steps_missing_rollback_notes_count",
        label="rollback note coverage",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="blast_radius_steps_missing_watchpoints_count",
        label="operational watchpoint coverage",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="dependency_audit_issue_count",
        label="dependency coherence",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )
    _compare_metric(
        baseline=baseline["metrics"],
        candidate=candidate["metrics"],
        key="parallel_ownership_issue_count",
        label="parallel ownership coherence",
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        lower_is_better=True,
    )

    if regressed and not improved:
        verdict = "weaker"
    elif improved and not regressed:
        verdict = "stronger"
    elif not improved and not regressed:
        verdict = "unchanged"
    else:
        verdict = "mixed"

    baseline_touched = set(baseline["sets"]["touched_paths"])
    candidate_touched = set(candidate["sets"]["touched_paths"])
    baseline_verify_targets = set(baseline["sets"]["verify_targets"])
    candidate_verify_targets = set(candidate["sets"]["verify_targets"])

    return {
        "verdict": verdict,
        "baseline": baseline,
        "candidate": candidate,
        "improved": improved,
        "regressed": regressed,
        "unchanged": unchanged,
        "added_touched_paths": sorted(candidate_touched - baseline_touched),
        "removed_touched_paths": sorted(baseline_touched - candidate_touched),
        "added_verify_targets": sorted(candidate_verify_targets - baseline_verify_targets),
        "removed_verify_targets": sorted(baseline_verify_targets - candidate_verify_targets),
    }


def render_plan_comparison(comparison: dict[str, Any], *, baseline_label: str, candidate_label: str) -> str:
    baseline_metrics = comparison["baseline"]["metrics"]
    candidate_metrics = comparison["candidate"]["metrics"]

    lines = [
        f"Plan comparison: `{baseline_label}` -> `{candidate_label}`",
        f"Verdict: {comparison['verdict']}",
        "",
        "Key metrics:",
        _metric_line("steps", baseline_metrics["steps_count"], candidate_metrics["steps_count"]),
        _metric_line(
            "unique touched files",
            baseline_metrics["unique_touched_paths_count"],
            candidate_metrics["unique_touched_paths_count"],
        ),
        _metric_line(
            "avg touched files per step",
            baseline_metrics["avg_touched_files_per_step"],
            candidate_metrics["avg_touched_files_per_step"],
        ),
        _metric_line(
            "max touched files in a step",
            baseline_metrics["max_touched_files_per_step"],
            candidate_metrics["max_touched_files_per_step"],
        ),
        _metric_line(
            "verification targets",
            baseline_metrics["unique_verify_targets_count"],
            candidate_metrics["unique_verify_targets_count"],
        ),
        _metric_line(
            "avg done_when per step",
            baseline_metrics["avg_done_when_per_step"],
            candidate_metrics["avg_done_when_per_step"],
        ),
        _metric_line(
            "missing constraints",
            baseline_metrics["steps_missing_constraints_count"],
            candidate_metrics["steps_missing_constraints_count"],
        ),
        _metric_line(
            "missing justifications",
            baseline_metrics["steps_missing_justification_count"],
            candidate_metrics["steps_missing_justification_count"],
        ),
        _metric_line(
            "missing files_read_first",
            baseline_metrics["steps_missing_files_read_first_count"],
            candidate_metrics["steps_missing_files_read_first_count"],
        ),
        _metric_line(
            "missing interfaces_to_preserve",
            baseline_metrics["steps_missing_interfaces_to_preserve_count"],
            candidate_metrics["steps_missing_interfaces_to_preserve_count"],
        ),
        _metric_line(
            "missing avoid_touching",
            baseline_metrics["steps_missing_avoid_touching_count"],
            candidate_metrics["steps_missing_avoid_touching_count"],
        ),
        _metric_line(
            "missing verification_targets",
            baseline_metrics["steps_missing_verification_targets_count"],
            candidate_metrics["steps_missing_verification_targets_count"],
        ),
        _metric_line(
            "missing wave",
            baseline_metrics["steps_missing_wave_count"],
            candidate_metrics["steps_missing_wave_count"],
        ),
        _metric_line(
            "missing file ownership",
            baseline_metrics["steps_missing_file_ownership_count"],
            candidate_metrics["steps_missing_file_ownership_count"],
        ),
        _metric_line(
            "risky steps missing rollback notes",
            baseline_metrics["risky_steps_missing_rollback_notes_count"],
            candidate_metrics["risky_steps_missing_rollback_notes_count"],
        ),
        _metric_line(
            "blast-radius steps missing watchpoints",
            baseline_metrics["blast_radius_steps_missing_watchpoints_count"],
            candidate_metrics["blast_radius_steps_missing_watchpoints_count"],
        ),
        _metric_line(
            "direct consumer audit issues",
            baseline_metrics["direct_consumer_audit_issue_count"],
            candidate_metrics["direct_consumer_audit_issue_count"],
        ),
        _metric_line(
            "dependency audit issues",
            baseline_metrics["dependency_audit_issue_count"],
            candidate_metrics["dependency_audit_issue_count"],
        ),
        _metric_line(
            "parallel ownership issues",
            baseline_metrics["parallel_ownership_issue_count"],
            candidate_metrics["parallel_ownership_issue_count"],
        ),
    ]

    lines.extend(_section_lines("Improvements", comparison["improved"]))
    lines.extend(_section_lines("Regressions", comparison["regressed"]))
    lines.extend(_section_lines("Unchanged", comparison["unchanged"]))
    lines.extend(_section_lines("New touched paths", comparison["added_touched_paths"]))
    lines.extend(_section_lines("Dropped touched paths", comparison["removed_touched_paths"]))
    lines.extend(_section_lines("New verification targets", comparison["added_verify_targets"]))
    lines.extend(_section_lines("Dropped verification targets", comparison["removed_verify_targets"]))
    lines.extend(_section_lines("Candidate warnings", comparison["candidate"]["warnings"]))

    return "\n".join(lines).rstrip()


def _planning_phase_header(state: dict[str, Any], phase_name: str) -> str:
    return (
        f"Feature request:\n{state['feature_request']}\n\n"
        f"Planning status: `{state['status']}`\n"
        f"Phase checkpoint: `{phase_name}`\n"
        f"Approved plan output: `{state['approved_plan_path']}`\n"
        f"Context artifact: `{state['context_path']}`\n"
        f"Discovery dossier: `{state['discovery_dossier_path']}`\n"
        f"Scope contract: `{state['scope_contract_path']}`\n"
        f"Architecture constraints: `{state['architecture_constraints_path']}`\n"
        f"Product scope audit: `{state['product_scope_audit_path']}`\n"
        f"Skeptic audit: `{state['skeptic_audit_path']}`\n"
        f"Convergence summary: `{state['convergence_summary_path']}`\n"
        f"Project memory: `{state['project_memory_path']}`\n"
        f"Requirements memory: `{state['requirements_memory_path']}`\n"
        f"Project state memory: `{state['state_memory_path']}`\n"
        f"Planning trace: `{state['planning_trace_path']}`"
    )


def _planning_phase_contract(state: dict[str, Any], *, phase_name: str) -> str:
    if phase_name == "discuss":
        return (
            "Current phase contract:\n"
            "- Inputs: feature request plus `PROJECT.md`, `REQUIREMENTS.md`, and `STATE.md`.\n"
            "- Output: `context.json` with goal, target user, desired behavior, defaults, non-goals, and success criteria.\n"
            "- Allowed work: clarify intent and durable constraints only; do not start discovery or plan drafting yet.\n"
            f"- When discuss outputs validate, run `{PLANNING_STATE_TOOL_COMMAND} advance discovery`.\n"
        )
    if phase_name == "discovery":
        return (
            "Current phase contract:\n"
            "- Inputs: validated `context.json` plus the repo memory docs.\n"
            "- Output: `discovery_dossier.json` with requirements, entry points, blast radius, pattern anchors, verification anchors, and open questions.\n"
            "- Allowed work: collect facts and codebase anchors only; do not lock architecture or author the implementation plan yet.\n"
            f"- When discovery outputs validate, run `{PLANNING_STATE_TOOL_COMMAND} advance architecture_audit`.\n"
        )
    if phase_name == "architecture_audit":
        return (
            "Current phase contract:\n"
            "- Inputs: validated discuss and discovery artifacts.\n"
            "- Output: `architecture_constraints.json` capturing required reuse, preserved interfaces, forbidden moves, and migration constraints.\n"
            "- Allowed work: define architecture guardrails only; do not revise scope or ship the final plan here.\n"
            f"- When architecture outputs validate, run `{PLANNING_STATE_TOOL_COMMAND} advance planning`.\n"
        )
    if phase_name == "planning":
        return (
            "Current phase contract:\n"
            "- Inputs: validated context, discovery, architecture constraints, and repo memory.\n"
            "- Outputs: `approved-plan.json` draft plus `scope_contract.json`.\n"
            "- Allowed work: produce the executable plan, wave/dependency metadata, and scope contract; do not skip scope pressure or skeptic review.\n"
            f"- When the plan draft validates, run `{PLANNING_STATE_TOOL_COMMAND} advance product_scope_audit`.\n"
        )
    if phase_name == "product_scope_audit":
        return (
            "Current phase contract:\n"
            "- Inputs: validated draft plan and scope contract.\n"
            "- Output: `product_scope_audit.json` with included scope, deferred scope, defaults taken, unresolved risks, and a pass/block recommendation.\n"
            "- Allowed work: trim scope and expose tradeoffs; do not add speculative work to the draft.\n"
            f"- When the scope audit passes, run `{PLANNING_STATE_TOOL_COMMAND} advance skeptic_audit`.\n"
        )
    if phase_name == "skeptic_audit":
        return (
            "Current phase contract:\n"
            "- Inputs: validated plan draft, scope audit, discovery dossier, and architecture constraints.\n"
            "- Output: `skeptic_audit.json` with objections, unresolved objections, and a pass/block recommendation.\n"
            "- Allowed work: surface feasibility, verification, dependency, and blast-radius risks; do not hide objections in prose.\n"
            f"- When the skeptic audit passes, run `{PLANNING_STATE_TOOL_COMMAND} advance convergence`.\n"
        )
    if phase_name == "convergence":
        return (
            "Current phase contract:\n"
            "- Inputs: validated plan draft, product scope audit, skeptic audit, and repo memory.\n"
            "- Output: `convergence_summary.json` with included scope, deferred scope, defaults taken, unresolved risks, and the approval summary.\n"
            "- Allowed work: merge the prior phases into one approval-facing package and repair the plan where the audits exposed drift.\n"
            f"- Before approval readiness, run `{PLANNING_STATE_TOOL_COMMAND} audit-plan` and fix every reported issue.\n"
            f"- When convergence outputs validate, run `{PLANNING_STATE_TOOL_COMMAND} advance approval_ready`.\n"
        )
    if phase_name == "approval_ready":
        return (
            "Current phase contract:\n"
            "- Inputs: every prior planning artifact plus a clean `audit-plan` result.\n"
            "- Output: an approval-ready `approved-plan.json` and `convergence_summary.json`.\n"
            "- Allowed work: present the scoped summary to the user and wait for explicit approval.\n"
        )
    raise ValueError(f"unsupported planning phase: {phase_name}")


def _validate_discuss_phase(state: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    context = _load_required_artifact(resolve_repo_path(state["context_path"]), "context artifact")
    if not _artifact_non_empty_string(context.get("goal")):
        issues.append("discuss phase requires context.goal")
    if not _artifact_non_empty_string(context.get("target_user")):
        issues.append("discuss phase requires context.target_user")
    if not _artifact_non_empty_string(context.get("desired_behavior")):
        issues.append("discuss phase requires context.desired_behavior")
    if not _artifact_string_list(context.get("success_criteria")):
        issues.append("discuss phase requires at least one context.success_criteria entry")
    issues.extend(
        _memory_section_issues(
            _load_memory_document(resolve_repo_path(state["project_memory_path"]), "project memory"),
            label="PROJECT.md",
            required_sections=["product intent", "target users", "durable constraints", "strategy", "current priorities"],
        )
    )
    issues.extend(
        _memory_section_issues(
            _load_memory_document(resolve_repo_path(state["requirements_memory_path"]), "requirements memory"),
            label="REQUIREMENTS.md",
            required_sections=["active backlog", "accepted requirements", "deferred scope", "milestone commitments"],
        )
    )
    issues.extend(
        _memory_section_issues(
            _load_memory_document(resolve_repo_path(state["state_memory_path"]), "state memory"),
            label="STATE.md",
            required_sections=["workflow status", "active initiative", "latest decisions", "release state", "unresolved risks"],
        )
    )
    return issues


def _validate_discovery_phase(state: dict[str, Any]) -> list[str]:
    issues = _validate_discuss_phase(state)
    discovery = load_discovery_dossier(resolve_repo_path(state["discovery_dossier_path"]))
    if discovery is None:
        return issues + ["discovery phase requires discovery_dossier.json"]
    current = discovery.get("current")
    if not isinstance(current, dict):
        return issues + ["discovery dossier is missing the current section"]
    if not _artifact_string_list(current.get("requirements")):
        issues.append("discovery phase requires current.requirements")
    if not _artifact_string_list(current.get("success_criteria")):
        issues.append("discovery phase requires current.success_criteria")
    anchors = []
    for field_name in ("entry_points", "pattern_anchors", "verification_anchors"):
        anchors.extend(_artifact_string_list(current.get(field_name)))
    if not anchors:
        issues.append(
            "discovery phase requires at least one entry point, pattern anchor, or verification anchor"
        )
    return issues


def _validate_architecture_audit_phase(state: dict[str, Any]) -> list[str]:
    issues = _validate_discovery_phase(state)
    architecture_constraints = _load_required_artifact(
        resolve_repo_path(state["architecture_constraints_path"]),
        "architecture constraints",
    )
    issues.extend(_audit_architecture_constraints(architecture_constraints))
    return issues


def _validate_planning_phase(state: dict[str, Any]) -> list[str]:
    issues = _validate_architecture_audit_phase(state)
    scope_contract = _load_required_artifact(resolve_repo_path(state["scope_contract_path"]), "scope contract")
    issues.extend(_audit_scope_contract(scope_contract))
    approved_plan_path = resolve_repo_path(state["approved_plan_path"])
    if not approved_plan_path.exists():
        return issues + [f"planning phase requires approved plan draft: {approved_plan_path}"]
    try:
        plan_spec = load_plan_spec(approved_plan_path)
    except Exception as exc:
        return issues + [f"planning phase approved plan draft is invalid: {exc}"]
    discovery = load_discovery_dossier(resolve_repo_path(state["discovery_dossier_path"])) or {}
    architecture_constraints = _load_required_artifact(
        resolve_repo_path(state["architecture_constraints_path"]),
        "architecture constraints",
    )
    issues.extend(
        _audit_plan_contract(
            plan_spec,
            discovery=discovery,
            scope_contract=scope_contract,
            architecture_constraints=architecture_constraints,
        )
    )
    return issues


def _validate_product_scope_audit_phase(state: dict[str, Any]) -> list[str]:
    issues = _validate_planning_phase(state)
    scope_audit = _load_required_artifact(
        resolve_repo_path(state["product_scope_audit_path"]),
        "product scope audit",
    )
    if not _artifact_string_list(scope_audit.get("included_scope")):
        issues.append("product_scope_audit phase requires included_scope")
    if not isinstance(scope_audit.get("defaults_taken"), list):
        issues.append("product_scope_audit phase requires defaults_taken")
    recommendation = str(scope_audit.get("recommendation") or "").strip().lower()
    if recommendation != "pass":
        issues.append("product_scope_audit phase requires recommendation=pass")
    return issues


def _validate_skeptic_audit_phase(state: dict[str, Any]) -> list[str]:
    issues = _validate_product_scope_audit_phase(state)
    skeptic_audit = _load_required_artifact(
        resolve_repo_path(state["skeptic_audit_path"]),
        "skeptic audit",
    )
    recommendation = str(skeptic_audit.get("recommendation") or "").strip().lower()
    if recommendation != "pass":
        issues.append("skeptic_audit phase requires recommendation=pass")
    unresolved = _artifact_string_list(skeptic_audit.get("unresolved_objections"))
    if unresolved:
        issues.append("skeptic_audit phase requires unresolved_objections to be empty")
    return issues


def _validate_convergence_phase(state: dict[str, Any]) -> list[str]:
    issues = _validate_skeptic_audit_phase(state)
    convergence_summary = _load_required_artifact(
        resolve_repo_path(state["convergence_summary_path"]),
        "convergence summary",
    )
    if not _artifact_string_list(convergence_summary.get("included_scope")):
        issues.append("convergence phase requires included_scope")
    if not isinstance(convergence_summary.get("deferred_scope"), list):
        issues.append("convergence phase requires deferred_scope")
    if not isinstance(convergence_summary.get("defaults_taken"), list):
        issues.append("convergence phase requires defaults_taken")
    if not _artifact_non_empty_string(convergence_summary.get("approval_summary")):
        issues.append("convergence phase requires approval_summary")
    return issues


def _validate_approval_ready_phase(state: dict[str, Any]) -> list[str]:
    issues = _validate_convergence_phase(state)
    issues.extend(audit_planning_artifacts(state))
    return issues


def resolve_repo_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def _planning_repo_root(planning_root: Path) -> Path:
    planning_root = planning_root.resolve()
    if planning_root.name == "workflow" and planning_root.parent.name == ".codex":
        return planning_root.parent.parent
    return planning_root


def _relative_or_source(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _present(value: bool) -> str:
    return "present" if value else "missing"


def _load_required_artifact(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"{label} not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _load_memory_document(path: Path, label: str) -> dict[str, list[str]]:
    if not path.exists():
        raise ValueError(f"{label} not found: {path}")
    sections = _parse_markdown_sections(path.read_text(encoding="utf-8"))
    if not sections:
        raise ValueError(f"{label} must contain markdown sections")
    return sections


def _parse_markdown_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            current_section = line[3:].strip().lower()
            sections.setdefault(current_section, [])
            continue
        if current_section is None:
            continue
        if line.startswith(("- ", "* ")):
            sections[current_section].append(line[2:].strip())
        else:
            sections[current_section].append(line)
    return {key: values for key, values in sections.items() if values}


def _memory_section_issues(
    sections: dict[str, list[str]],
    *,
    label: str,
    required_sections: list[str],
) -> list[str]:
    issues: list[str] = []
    for section_name in required_sections:
        if not sections.get(section_name):
            issues.append(f"{label} is missing the `{section_name}` section")
    return issues


def _artifact_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _artifact_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
    return normalized


def _ensure_discovery_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"discovery {field_name} must be a list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"discovery {field_name} must contain non-empty strings")
        normalized.append(item.strip())
    return normalized


def _extract_verify_targets(commands: list[str]) -> list[str]:
    targets: list[str] = []
    for command in commands:
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
        for token in tokens:
            if not _looks_like_repo_path(token):
                continue
            if token.startswith("-"):
                continue
            if token.startswith(("tests/", "app/", ".codex/")):
                targets.append(token.rstrip(","))
    return sorted(dict.fromkeys(targets))


def _compare_metric(
    *,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    key: str,
    label: str,
    improved: list[str],
    regressed: list[str],
    unchanged: list[str],
    lower_is_better: bool,
) -> None:
    baseline_value = baseline[key]
    candidate_value = candidate[key]
    if baseline_value == candidate_value:
        unchanged.append(f"{label}: unchanged ({baseline_value})")
        return

    got_better = candidate_value < baseline_value if lower_is_better else candidate_value > baseline_value
    summary = f"{label}: {baseline_value} -> {candidate_value}"
    if got_better:
        improved.append(summary)
    else:
        regressed.append(summary)


def _metric_line(label: str, baseline_value: Any, candidate_value: Any) -> str:
    return f"- {label}: {baseline_value} -> {candidate_value}"


def _section_lines(title: str, items: list[str]) -> list[str]:
    if not items:
        return []
    lines = ["", f"{title}:"]
    lines.extend(f"- {item}" for item in items)
    return lines


def _impacted_entry_points_for_step(step: dict[str, Any], entry_points: list[str]) -> list[str]:
    scoped_paths: set[str] = set()
    for field_name in ("planned_updates", "planned_creates"):
        value = step.get(field_name, [])
        if isinstance(value, list):
            scoped_paths.update(item.strip() for item in value if isinstance(item, str) and item.strip())
    return [entry_point for entry_point in entry_points if entry_point in scoped_paths]


def _step_requires_direct_coverage(step: dict[str, Any], requirements_by_id: dict[str, dict[str, Any]]) -> bool:
    kinds: set[str] = set()
    for requirement_id in step.get("requirement_ids", []):
        requirement = requirements_by_id.get(str(requirement_id))
        if not requirement:
            continue
        requirement_kind = requirement.get("kind")
        if isinstance(requirement_kind, str) and requirement_kind.strip():
            kinds.add(requirement_kind.strip().lower())

    if "verification" in kinds:
        return True

    step_text = " ".join(
        str(value).lower()
        for value in (
            step.get("title", ""),
            step.get("goal", ""),
            *step.get("constraints", []),
        )
    )
    return any(keyword in step_text for keyword in DIRECT_COVERAGE_KEYWORDS)


def _direct_verification_targets_for_entry_points(entry_points: list[str]) -> list[str]:
    targets: list[str] = []
    for entry_point in entry_points:
        if not entry_point.startswith("app/") or not entry_point.endswith(".py"):
            continue
        source_path = Path(entry_point)
        relative_path = source_path.relative_to("app")
        test_path = Path("tests") / relative_path.parent / f"test_{relative_path.name}"
        if (ROOT_DIR / test_path).exists():
            targets.append(str(test_path))
    return sorted(dict.fromkeys(targets))


def _plan_text(plan_spec: dict[str, Any]) -> str:
    return "\n".join(
        [
            str(plan_spec.get("workflow_name") or ""),
            str(plan_spec.get("summary") or ""),
            *(
                str(requirement.get("text") or "")
                for requirement in plan_spec.get("requirements", [])
                if isinstance(requirement, dict)
            ),
            *(
                "\n".join(
                    [
                        str(step.get("title") or ""),
                        str(step.get("goal") or ""),
                        str(step.get("justification") or ""),
                        *[str(item) for item in _artifact_string_list(step.get("constraints"))],
                        *[str(item) for item in _artifact_string_list(step.get("done_when"))],
                        *[str(item) for item in _artifact_string_list(step.get("interfaces_to_preserve"))],
                        *[str(item) for item in _artifact_string_list(step.get("risk_flags"))],
                    ]
                )
                for step in plan_spec.get("steps", [])
                if isinstance(step, dict)
            ),
        ]
    ).lower()


def _audit_step_dependencies(
    *,
    steps_by_id: dict[str, dict[str, Any]],
    step_order: dict[str, int],
    step_waves: dict[str, int],
    step_dependencies: dict[str, list[str]],
) -> list[str]:
    issues: list[str] = []
    for step_id, dependencies in step_dependencies.items():
        for dependency_id in dependencies:
            if dependency_id not in steps_by_id:
                issues.append(f"step {step_id} depends_on unknown step `{dependency_id}`")
                continue
            if dependency_id == step_id:
                issues.append(f"step {step_id} cannot depend on itself")
                continue
            if step_order[step_id] <= step_order[dependency_id]:
                issues.append(f"step {step_id} must appear after dependency `{dependency_id}`")
            if step_id in step_waves and dependency_id in step_waves:
                if step_waves[step_id] <= step_waves[dependency_id]:
                    issues.append(
                        f"step {step_id} wave {step_waves[step_id]} must be greater than dependency "
                        f"{dependency_id} wave {step_waves[dependency_id]}"
                    )

    cycle = _dependency_cycle(step_dependencies)
    if cycle:
        issues.append("dependency cycle detected: " + " -> ".join(cycle))
    return issues


def _dependency_cycle(step_dependencies: dict[str, list[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(step_id: str) -> list[str]:
        if step_id in visited:
            return []
        if step_id in visiting:
            cycle_start = stack.index(step_id)
            return stack[cycle_start:] + [step_id]

        visiting.add(step_id)
        stack.append(step_id)
        for dependency_id in step_dependencies.get(step_id, []):
            cycle = visit(dependency_id)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(step_id)
        visited.add(step_id)
        return []

    for step_id in step_dependencies:
        cycle = visit(step_id)
        if cycle:
            return cycle
    return []


def _audit_parallel_file_ownership(
    wave_ownership: dict[int, list[tuple[str, list[str]]]],
) -> list[str]:
    issues: list[str] = []
    for wave, owners in wave_ownership.items():
        for left_index, (left_step_id, left_paths) in enumerate(owners):
            for right_step_id, right_paths in owners[left_index + 1 :]:
                conflicts = sorted(
                    {
                        _shared_repo_path(left_path, right_path)
                        for left_path in left_paths
                        for right_path in right_paths
                        if _repo_paths_overlap(left_path, right_path)
                    }
                )
                if conflicts:
                    issues.append(
                        f"wave {wave} has conflicting file ownership between {left_step_id} and {right_step_id}: "
                        + ", ".join(conflicts)
                    )
    return issues


def _repo_path_covers(owner_path: str, target_path: str) -> bool:
    owner = owner_path.rstrip("/")
    target = target_path.rstrip("/")
    return owner == target or target.startswith(owner + "/")


def _repo_paths_overlap(left_path: str, right_path: str) -> bool:
    left = left_path.rstrip("/")
    right = right_path.rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _shared_repo_path(left_path: str, right_path: str) -> str:
    left = left_path.rstrip("/")
    right = right_path.rstrip("/")
    if left == right:
        return left
    if left.startswith(right + "/"):
        return right
    if right.startswith(left + "/"):
        return left
    return f"{left} <-> {right}"


def _default_project_memory() -> str:
    return """# Project

## Product Intent
- Build a kernel-first repo-local workflow that turns planning and execution control into auditable code.

## Target Users
- Maintainers using Codex to plan, implement, review, and ship changes inside a live repository checkout.

## Durable Constraints
- Keep `$workflow` as the canonical interface and `/workflow` as compatibility-only.
- Keep workflow state deterministic, on disk, and easy to audit.
- Prefer small repo-local utilities over framework-heavy abstractions.

## Strategy
- Stabilize the workflow kernel before revisiting packaging or distribution shape.

## Current Priorities
- Enforce planning phases as code.
- Add repo-root project memory.
- Make approved plans orchestration-ready.
"""


def _default_requirements_memory() -> str:
    return """# Requirements

## Active Backlog
- Enforce hard planning phase gates with deterministic transitions.
- Add repo-root project memory that planning can read and audit.
- Extend the approved plan schema with orchestration metadata.

## Accepted Requirements
- Approved plans must pass audit before execution starts.
- Execution must preserve review and ship gates.
- Parallel-ready plans must declare ownership and dependency metadata.

## Deferred Scope
- Post-implementation UAT and gap-closure loops.
- Local telemetry scorecards.
- Greenfield bootstrap mode.

## Milestone Commitments
- Land hard phase gates, repo memory, and orchestration metadata together before broader packaging work.
"""


def _default_state_memory() -> str:
    return """# State

## Workflow Status
- Kernel upgrade in progress.

## Active Initiative
- Hard planning gates, repo memory, and orchestration-ready plans.

## Latest Decisions
- Treat execution handoff metadata as part of the kernel.
- Keep `$workflow` as the primary interface and `$ship` as the terminal publish skill.

## Release State
- Pre-kernel-stabilization.

## Unresolved Risks
- UAT, telemetry, and bootstrap mode remain intentionally deferred until the kernel milestone is stable.
"""
