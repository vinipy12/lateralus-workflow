from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = WORKFLOW_DIR / "state.json"
DEFAULT_UAT_ARTIFACT_PATH = WORKFLOW_DIR / "uat.json"
DEFAULT_METRICS_DIR = WORKFLOW_DIR / "metrics"
STATE_EXAMPLE_PATH = WORKFLOW_DIR / "state.example.json"
STATE_SCHEMA_PATH = WORKFLOW_DIR / "state.schema.json"
PLAN_SCHEMA_PATH = WORKFLOW_DIR / "plan.schema.json"
SKILL_SCRIPTS_DIR = os.environ.get("LATERALUS_WORKFLOW_SKILL_SCRIPTS_DIR")
STATE_TOOL_COMMAND = (
    f"python3 {shlex.quote(str(Path(SKILL_SCRIPTS_DIR) / 'workflow_state.py'))}"
    if SKILL_SCRIPTS_DIR
    else "python3 .codex/workflow/scripts/workflow_state.py"
)
DEFAULT_REVIEW_PATH = "code_review.md"
DEFAULT_SHIP_SKILL = "ship"
DEFAULT_BASE_BRANCH = "origin/main"

VALID_WORKFLOW_STATUSES = {
    "active",
    "execution_escalated",
    "uat_pending",
    "gap_closure_pending",
    "replan_required",
    "ship_pending",
    "complete",
}
VALID_MODES = {"stepwise", "ship"}
VALID_STEP_STATUSES = {
    "pending",
    "implementing",
    "review_pending",
    "fix_pending",
    "commit_pending",
    "committed",
    "shipped",
}
VALID_UAT_STATUSES = {"pending", "passed", "failed_gap", "failed_replan"}
VALID_ESCALATION_CODES = {
    "verification_missing",
    "verification_failed",
    "ownership_mismatch",
    "agents_update_required",
    "review_required",
    "uat_replan_required",
    "manual_override",
    "unknown_blocker",
}
REVIEW_PENDING_ENTRY_STATUSES = {"implementing", "fix_pending", "review_pending"}


@dataclass(frozen=True)
class WorkflowDecision:
    action: str
    prompt: str | None = None


def load_state(path: Path = DEFAULT_STATE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data = _normalize_state_compat(data, path)
    validate_state(data)
    return data


def save_state(state: dict[str, Any], path: Path = DEFAULT_STATE_PATH) -> None:
    validate_state(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def validate_state(state: dict[str, Any]) -> None:
    required_fields = {
        "version",
        "workflow_name",
        "workflow_status",
        "escalation",
        "mode",
        "plan_path",
        "review_path",
        "ship_skill",
        "current_step_id",
        "base_branch",
        "request_codex_review",
        "uat_artifact_path",
        "metrics_dir",
        "steps",
    }
    missing = sorted(required_fields - state.keys())
    if missing:
        raise ValueError(f"workflow state missing required fields: {', '.join(missing)}")

    if state["version"] != 1:
        raise ValueError("workflow state version must be 1")
    if state["workflow_status"] not in VALID_WORKFLOW_STATUSES:
        raise ValueError(f"invalid workflow_status: {state['workflow_status']}")
    _validate_escalation(state["escalation"])
    if state["workflow_status"] == "execution_escalated" and state["escalation"] is None:
        raise ValueError("execution_escalated workflow_status requires escalation metadata")
    if state["workflow_status"] != "execution_escalated" and state["escalation"] is not None:
        raise ValueError("escalation metadata must be null unless workflow_status is execution_escalated")
    if state["mode"] not in VALID_MODES:
        raise ValueError(f"invalid mode: {state['mode']}")
    if not isinstance(state["request_codex_review"], bool):
        raise ValueError("request_codex_review must be a boolean")
    for field_name in ("workflow_name", "plan_path", "review_path", "ship_skill", "current_step_id", "base_branch"):
        if not isinstance(state[field_name], str) or not state[field_name].strip():
            raise ValueError(f"{field_name} must be a non-empty string")
    for field_name in ("uat_artifact_path", "metrics_dir"):
        if not isinstance(state[field_name], str) or not state[field_name].strip():
            raise ValueError(f"{field_name} must be a non-empty string")

    steps = state["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must be a non-empty list")

    step_ids: set[str] = set()
    for step in steps:
        _validate_step(step)
        if step["id"] in step_ids:
            raise ValueError(f"duplicate step id: {step['id']}")
        step_ids.add(step["id"])

    if state["current_step_id"] not in step_ids:
        raise ValueError("current_step_id must reference one of the steps")


def load_plan_spec(path: Path, plan_id: str | None = None) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"plan source not found: {path}")

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        spec = json.loads(text)
        return _select_plan_spec(_coerce_plan_specs(spec, path), plan_id=plan_id)

    specs = _extract_plan_specs_from_markdown(text, source_path=path)

    if not specs:
        raise ValueError(
            "no plan spec found; use a JSON file or a markdown fenced block containing a workflow object"
        )

    return _select_plan_spec(specs, plan_id=plan_id)


def build_state_from_plan_spec(
    plan_spec: dict[str, Any],
    *,
    plan_path: str,
    review_path: str = DEFAULT_REVIEW_PATH,
    ship_skill: str = DEFAULT_SHIP_SKILL,
    base_branch: str = DEFAULT_BASE_BRANCH,
    mode: str = "ship",
    request_codex_review: bool = True,
    uat_artifact_path: str = ".codex/workflow/uat.json",
    metrics_dir: str = ".codex/workflow/metrics",
) -> dict[str, Any]:
    validate_plan_spec(plan_spec)

    steps_input = plan_spec.get("steps")
    if not isinstance(steps_input, list) or not steps_input:
        raise ValueError("plan spec must contain a non-empty steps array")

    workflow_mode = plan_spec.get("mode", mode)
    if workflow_mode not in VALID_MODES:
        raise ValueError(f"invalid plan mode: {workflow_mode}")

    normalized_steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(steps_input, start=1):
        normalized_steps.append(_normalize_plan_step(raw_step, index=index))

    workflow_name = str(plan_spec.get("workflow_name") or plan_spec.get("plan_id") or Path(plan_path).stem).strip()
    if not workflow_name:
        raise ValueError("workflow_name must be provided or derivable from the plan source")

    return {
        "version": 1,
        "workflow_name": workflow_name,
        "workflow_status": "active",
        "escalation": None,
        "mode": workflow_mode,
        "plan_path": plan_spec.get("plan_path", plan_path),
        "review_path": plan_spec.get("review_path", review_path),
        "ship_skill": plan_spec.get("ship_skill", ship_skill),
        "current_step_id": normalized_steps[0]["id"],
        "base_branch": plan_spec.get("base_branch", base_branch),
        "request_codex_review": bool(plan_spec.get("request_codex_review", request_codex_review)),
        "uat_artifact_path": str(plan_spec.get("uat_artifact_path", uat_artifact_path)),
        "metrics_dir": str(plan_spec.get("metrics_dir", metrics_dir)),
        "steps": normalized_steps,
    }


def load_uat_artifact(path: Path = DEFAULT_UAT_ARTIFACT_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_uat_artifact(data)
    return data


def save_uat_artifact(artifact: dict[str, Any], path: Path = DEFAULT_UAT_ARTIFACT_PATH) -> None:
    validate_uat_artifact(artifact)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


def validate_uat_artifact(artifact: dict[str, Any]) -> None:
    required_fields = {
        "version",
        "workflow_name",
        "plan_path",
        "generated_from",
        "overall_status",
        "summary",
        "checklist",
    }
    missing = sorted(required_fields - artifact.keys())
    if missing:
        raise ValueError(f"uat artifact missing required fields: {', '.join(missing)}")

    if artifact["version"] != 1:
        raise ValueError("uat artifact version must be 1")
    for field_name in ("workflow_name", "plan_path"):
        if not isinstance(artifact[field_name], str) or not artifact[field_name].strip():
            raise ValueError(f"{field_name} must be a non-empty string in the uat artifact")
    if artifact["overall_status"] not in VALID_UAT_STATUSES:
        raise ValueError(f"invalid uat overall_status: {artifact['overall_status']}")
    if not isinstance(artifact["summary"], (str, type(None))):
        raise ValueError("uat summary must be a string or null")

    generated_from = artifact["generated_from"]
    if not isinstance(generated_from, dict):
        raise ValueError("uat generated_from must be an object")
    for field_name in ("project_memory_path", "requirements_memory_path", "state_memory_path"):
        value = generated_from.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"uat generated_from.{field_name} must be a non-empty string")

    checklist = artifact["checklist"]
    if not isinstance(checklist, list) or not checklist:
        raise ValueError("uat checklist must be a non-empty list")
    seen_ids: set[str] = set()
    for item in checklist:
        if not isinstance(item, dict):
            raise ValueError("uat checklist entries must be objects")
        required_item_fields = {
            "id",
            "title",
            "requirement_ids",
            "prompt",
            "verification_targets",
            "status",
        }
        missing_item_fields = sorted(required_item_fields - item.keys())
        if missing_item_fields:
            raise ValueError(
                "uat checklist entry missing fields: " + ", ".join(missing_item_fields)
            )
        item_id = item["id"]
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("uat checklist id must be a non-empty string")
        if item_id in seen_ids:
            raise ValueError(f"duplicate uat checklist id: {item_id}")
        seen_ids.add(item_id)
        for field_name in ("title", "prompt"):
            value = item[field_name]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"uat checklist {field_name} must be a non-empty string for {item_id}")
        if item["status"] not in VALID_UAT_STATUSES:
            raise ValueError(f"invalid uat checklist status for {item_id}: {item['status']}")
        for list_name in ("requirement_ids", "verification_targets"):
            if not isinstance(item[list_name], list):
                raise ValueError(f"uat checklist {list_name} must be a list for {item_id}")
            for value in item[list_name]:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"uat checklist {list_name} must contain non-empty strings for {item_id}")


def build_uat_artifact(
    plan_spec: dict[str, Any],
    *,
    workflow_name: str,
    plan_path: str,
    project_memory_path: str,
    requirements_memory_path: str,
    state_memory_path: str,
) -> dict[str, Any]:
    validate_plan_spec(plan_spec)
    checklist: list[dict[str, Any]] = []
    steps = [step for step in plan_spec.get("steps", []) if isinstance(step, dict)]

    for requirement in plan_spec.get("requirements", []):
        requirement_id = str(requirement["id"])
        matching_steps = [
            step
            for step in steps
            if requirement_id in _ensure_string_list(
                step.get("requirement_ids", []),
                field_name=f"requirement_ids for {step.get('id', '<unknown>')}",
            )
        ]
        verification_targets: list[str] = []
        for step in matching_steps:
            targets = _ensure_string_list(
                step.get("verification_targets", []),
                field_name=f"verification_targets for {step.get('id', '<unknown>')}",
            )
            if not targets:
                targets = _extract_verify_targets(
                    _ensure_string_list(
                        step.get("verify_cmds", []),
                        field_name=f"verify_cmds for {step.get('id', '<unknown>')}",
                    )
                )
            verification_targets.extend(targets)
        checklist.append(
            {
                "id": f"requirement-{requirement_id}",
                "title": f"{requirement_id}: {requirement['text']}",
                "requirement_ids": [requirement_id],
                "prompt": (
                    f"Confirm that the committed implementation satisfies requirement {requirement_id}: "
                    f"{requirement['text']}"
                ),
                "verification_targets": _unique_preserving_order(verification_targets),
                "status": "pending",
            }
        )

    checklist.append(
        {
            "id": "repo-memory-consistency",
            "title": "Repo memory consistency",
            "requirement_ids": [],
            "prompt": (
                "Confirm the shipped scope and behavior still match durable constraints in PROJECT.md, "
                "accepted and deferred scope in REQUIREMENTS.md, and the current delivery record in STATE.md."
            ),
            "verification_targets": [
                project_memory_path,
                requirements_memory_path,
                state_memory_path,
            ],
            "status": "pending",
        }
    )

    artifact = {
        "version": 1,
        "workflow_name": workflow_name,
        "plan_path": plan_path,
        "generated_from": {
            "project_memory_path": project_memory_path,
            "requirements_memory_path": requirements_memory_path,
            "state_memory_path": state_memory_path,
        },
        "overall_status": "pending",
        "summary": None,
        "checklist": checklist,
    }
    validate_uat_artifact(artifact)
    return artifact


def reset_uat_artifact_for_rerun(path: Path) -> dict[str, Any]:
    artifact = load_uat_artifact(path)
    if artifact is None:
        raise ValueError(f"uat artifact not found: {path}")
    artifact["overall_status"] = "pending"
    for item in artifact["checklist"]:
        item["status"] = "pending"
    save_uat_artifact(artifact, path)
    return artifact


def update_uat_artifact_result(path: Path, status: str, summary: str | None) -> dict[str, Any]:
    artifact = load_uat_artifact(path)
    if artifact is None:
        raise ValueError(f"uat artifact not found: {path}")
    if status not in {"passed", "failed_gap", "failed_replan"}:
        raise ValueError(f"invalid uat result: {status}")
    artifact["overall_status"] = status
    artifact["summary"] = summary
    for item in artifact["checklist"]:
        item["status"] = status
    save_uat_artifact(artifact, path)
    return artifact


def _validate_step(step: dict[str, Any]) -> None:
    required_fields = {
        "id",
        "title",
        "goal",
        "context",
        "constraints",
        "done_when",
        "verify_cmds",
        "agents_paths",
        "commit_message",
        "status",
        "review_summary",
    }
    missing = sorted(required_fields - step.keys())
    if missing:
        raise ValueError(f"step {step.get('id', '<unknown>')} missing fields: {', '.join(missing)}")
    if step["status"] not in VALID_STEP_STATUSES:
        raise ValueError(f"invalid step status for {step['id']}: {step['status']}")
    if not isinstance(step["review_summary"], (str, type(None))):
        raise ValueError(f"review_summary must be a string or null for {step['id']}")
    for field_name in (
        "id",
        "title",
        "goal",
        "commit_message",
    ):
        if not isinstance(step[field_name], str) or not step[field_name].strip():
            raise ValueError(f"{field_name} must be a non-empty string for {step['id']}")
    for list_name in ("context", "constraints", "done_when", "verify_cmds", "agents_paths"):
        if not isinstance(step[list_name], list):
            raise ValueError(f"{list_name} must be a list for {step['id']}")
        for item in step[list_name]:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{list_name} must contain non-empty strings for {step['id']}")
    if "justification" in step and (
        not isinstance(step["justification"], str) or not step["justification"].strip()
    ):
        raise ValueError(f"justification must be a non-empty string for {step['id']}")
    for list_name in (
        "files_read_first",
        "interfaces_to_preserve",
        "avoid_touching",
        "verification_targets",
        "risk_flags",
        "blast_radius",
        "decision_ids",
        "depends_on",
        "file_ownership",
        "rollback_notes",
        "operational_watchpoints",
    ):
        if list_name not in step:
            continue
        if not isinstance(step[list_name], list):
            raise ValueError(f"{list_name} must be a list for {step['id']}")
        for item in step[list_name]:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{list_name} must contain non-empty strings for {step['id']}")
    if "wave" in step and not _is_positive_int(step["wave"]):
        raise ValueError(f"wave must be a positive integer for {step['id']}")


def _coerce_plan_specs(parsed: Any, source_path: Path) -> list[dict[str, Any]]:
    if isinstance(parsed, dict):
        if isinstance(parsed.get("plans"), list):
            specs = []
            for item in parsed["plans"]:
                if not isinstance(item, dict):
                    raise ValueError(f"plan entries in {source_path} must be objects")
                specs.append(item)
            return specs
        return [parsed]
    raise ValueError(f"unsupported plan payload in {source_path}; expected an object")


def _extract_plan_specs_from_markdown(text: str, *, source_path: Path) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    fence: str | None = None
    buffer: list[str] = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if fence is None:
            if stripped.startswith("```"):
                language = stripped[3:].strip()
                if language in {"", "json", "codex-plan"}:
                    fence = language
                    buffer = []
            continue

        if stripped.startswith("```"):
            body = "\n".join(buffer).strip()
            if body:
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    pass
                else:
                    specs.extend(_coerce_plan_specs(parsed, source_path))
            fence = None
            buffer = []
            continue

        buffer.append(raw_line)

    return specs


def _select_plan_spec(specs: list[dict[str, Any]], *, plan_id: str | None) -> dict[str, Any]:
    if plan_id is None:
        if len(specs) != 1:
            available = ", ".join(sorted(str(spec.get("plan_id", "<missing>")) for spec in specs))
            raise ValueError(f"multiple plan specs found; choose one with --plan-id ({available})")
        selected = specs[0]
        validate_plan_spec(selected)
        return selected

    for spec in specs:
        if spec.get("plan_id") == plan_id:
            validate_plan_spec(spec)
            return spec
    raise ValueError(f"plan_id not found: {plan_id}")


def _normalize_plan_step(raw_step: dict[str, Any], *, index: int) -> dict[str, Any]:
    if not isinstance(raw_step, dict):
        raise ValueError(f"step {index} must be an object")

    title = str(raw_step.get("title") or "").strip()
    goal = str(raw_step.get("goal") or "").strip()
    if not title:
        raise ValueError(f"step {index} is missing title")
    if not goal:
        raise ValueError(f"step {index} is missing goal")

    step_id = str(raw_step.get("id") or f"step-{index}").strip()
    if not step_id:
        raise ValueError(f"step {index} produced an empty id")

    context = _ensure_string_list(raw_step.get("context", []), field_name=f"context for {step_id}")
    constraints = _ensure_string_list(raw_step.get("constraints", []), field_name=f"constraints for {step_id}")
    done_when = _ensure_string_list(raw_step.get("done_when", []), field_name=f"done_when for {step_id}")
    verify_cmds = _ensure_string_list(raw_step.get("verify_cmds", []), field_name=f"verify_cmds for {step_id}")
    agents_paths = _ensure_string_list(raw_step.get("agents_paths", []), field_name=f"agents_paths for {step_id}")
    if not agents_paths:
        agents_paths = infer_agents_paths(context)
    if not agents_paths:
        agents_paths = ["AGENTS.md"]

    commit_message = str(raw_step.get("commit_message") or "").strip()
    if not commit_message:
        raise ValueError(f"step {step_id} is missing commit_message")

    status = str(raw_step.get("status") or ("implementing" if index == 1 else "pending")).strip()
    if status not in VALID_STEP_STATUSES:
        raise ValueError(f"invalid status for {step_id}: {status}")

    review_summary = raw_step.get("review_summary")
    if review_summary is not None and not isinstance(review_summary, str):
        raise ValueError(f"review_summary must be a string or null for {step_id}")

    normalized_step = {
        "id": step_id,
        "title": title,
        "goal": goal,
        "context": context,
        "constraints": constraints,
        "done_when": done_when,
        "verify_cmds": verify_cmds,
        "agents_paths": agents_paths,
        "commit_message": commit_message,
        "status": status,
        "review_summary": review_summary,
    }
    justification = str(raw_step.get("justification") or "").strip()
    if justification:
        normalized_step["justification"] = justification

    for list_name in (
        "files_read_first",
        "interfaces_to_preserve",
        "avoid_touching",
        "verification_targets",
        "risk_flags",
        "blast_radius",
        "decision_ids",
        "depends_on",
        "file_ownership",
        "rollback_notes",
        "operational_watchpoints",
    ):
        values = _ensure_string_list(raw_step.get(list_name, []), field_name=f"{list_name} for {step_id}")
        if values:
            normalized_step[list_name] = values
    wave = raw_step.get("wave")
    if wave is not None:
        if not _is_positive_int(wave):
            raise ValueError(f"wave must be a positive integer for {step_id}")
        normalized_step["wave"] = wave

    return normalized_step


def validate_plan_spec(plan_spec: dict[str, Any]) -> None:
    if not isinstance(plan_spec, dict):
        raise ValueError("plan spec must be an object")

    allowed_fields = {
        "plan_id",
        "workflow_name",
        "summary",
        "mode",
        "base_branch",
        "review_path",
        "ship_skill",
        "request_codex_review",
        "requirements",
        "assumptions",
        "open_questions",
        "out_of_scope",
        "steps",
    }
    unknown_fields = sorted(set(plan_spec.keys()) - allowed_fields)
    if unknown_fields:
        raise ValueError(f"plan spec contains unsupported fields: {', '.join(unknown_fields)}")

    required_fields = {
        "workflow_name",
        "summary",
        "requirements",
        "assumptions",
        "open_questions",
        "out_of_scope",
        "steps",
    }
    missing = sorted(required_fields - plan_spec.keys())
    if missing:
        raise ValueError(f"plan spec missing required fields: {', '.join(missing)}")

    for field_name in ("workflow_name", "summary"):
        if not isinstance(plan_spec[field_name], str) or not plan_spec[field_name].strip():
            raise ValueError(f"{field_name} must be a non-empty string")

    if "plan_id" in plan_spec and (
        not isinstance(plan_spec["plan_id"], str) or not plan_spec["plan_id"].strip()
    ):
        raise ValueError("plan_id must be a non-empty string when provided")

    if "mode" in plan_spec and plan_spec["mode"] not in VALID_MODES:
        raise ValueError(f"invalid plan mode: {plan_spec['mode']}")

    if "request_codex_review" in plan_spec and not isinstance(plan_spec["request_codex_review"], bool):
        raise ValueError("request_codex_review must be a boolean")

    for field_name in ("base_branch", "review_path", "ship_skill"):
        if field_name in plan_spec and (
            not isinstance(plan_spec[field_name], str) or not plan_spec[field_name].strip()
        ):
            raise ValueError(f"{field_name} must be a non-empty string when provided")

    requirement_ids = _validate_requirements(plan_spec["requirements"])
    for field_name in ("assumptions", "open_questions", "out_of_scope"):
        _ensure_string_list(plan_spec[field_name], field_name=field_name)

    steps = plan_spec["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must be a non-empty list")

    seen_step_ids: set[str] = set()
    covered_requirement_ids: set[str] = set()
    for index, step in enumerate(steps, start=1):
        step_id, step_requirement_ids = _validate_plan_step(
            step,
            index=index,
            valid_requirement_ids=requirement_ids,
        )
        if step_id in seen_step_ids:
            raise ValueError(f"duplicate step id: {step_id}")
        seen_step_ids.add(step_id)
        covered_requirement_ids.update(step_requirement_ids)

    missing_coverage = sorted(requirement_ids - covered_requirement_ids)
    if missing_coverage:
        raise ValueError(f"requirements missing step coverage: {', '.join(missing_coverage)}")


def _validate_requirements(requirements: Any) -> set[str]:
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("requirements must be a non-empty list")

    seen: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            raise ValueError("requirements must contain objects")

        unknown_fields = sorted(set(requirement.keys()) - {"id", "text", "kind"})
        if unknown_fields:
            raise ValueError(
                "requirement entries contain unsupported fields: " + ", ".join(unknown_fields)
            )

        requirement_id = requirement.get("id")
        text = requirement.get("text")
        if not isinstance(requirement_id, str) or not requirement_id.strip():
            raise ValueError("each requirement must have a non-empty id")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"requirement {requirement_id!r} must have non-empty text")
        if requirement_id in seen:
            raise ValueError(f"duplicate requirement id: {requirement_id}")
        if "kind" in requirement and (
            not isinstance(requirement["kind"], str) or not requirement["kind"].strip()
        ):
            raise ValueError(f"requirement {requirement_id!r} kind must be a non-empty string")
        seen.add(requirement_id)
    return seen


def _validate_plan_step(
    step: Any,
    *,
    index: int,
    valid_requirement_ids: set[str],
) -> tuple[str, set[str]]:
    if not isinstance(step, dict):
        raise ValueError(f"step {index} must be an object")

    allowed_fields = {
        "id",
        "title",
        "goal",
        "requirement_ids",
        "context",
        "planned_updates",
        "planned_creates",
        "constraints",
        "done_when",
        "verify_cmds",
        "agents_paths",
        "commit_message",
        "justification",
        "files_read_first",
        "interfaces_to_preserve",
        "avoid_touching",
        "verification_targets",
        "risk_flags",
        "blast_radius",
        "decision_ids",
        "depends_on",
        "wave",
        "file_ownership",
        "rollback_notes",
        "operational_watchpoints",
    }
    unknown_fields = sorted(set(step.keys()) - allowed_fields)
    if unknown_fields:
        raise ValueError(f"step {index} contains unsupported fields: {', '.join(unknown_fields)}")

    required_fields = {
        "title",
        "goal",
        "requirement_ids",
        "context",
        "planned_updates",
        "planned_creates",
        "constraints",
        "done_when",
        "verify_cmds",
        "commit_message",
    }
    missing = sorted(required_fields - step.keys())
    if missing:
        raise ValueError(f"step {index} missing required fields: {', '.join(missing)}")

    step_id = str(step.get("id") or f"step-{index}").strip()
    if not step_id:
        raise ValueError(f"step {index} produced an empty id")

    for field_name in ("title", "goal", "commit_message"):
        if not isinstance(step[field_name], str) or not step[field_name].strip():
            raise ValueError(f"{field_name} must be a non-empty string for {step_id}")

    requirement_ids = _ensure_string_list(step["requirement_ids"], field_name=f"requirement_ids for {step_id}")
    if not requirement_ids:
        raise ValueError(f"requirement_ids must be non-empty for {step_id}")

    unknown_requirement_ids = sorted(set(requirement_ids) - valid_requirement_ids)
    if unknown_requirement_ids:
        raise ValueError(
            f"step {step_id} references unknown requirement ids: {', '.join(unknown_requirement_ids)}"
        )

    for list_name in (
        "context",
        "planned_updates",
        "planned_creates",
        "constraints",
        "done_when",
        "verify_cmds",
    ):
        values = _ensure_string_list(step[list_name], field_name=f"{list_name} for {step_id}")
        if list_name in {"context", "planned_updates", "done_when", "verify_cmds"} and not values:
            raise ValueError(f"{list_name} must be non-empty for {step_id}")

    if "agents_paths" in step:
        _ensure_string_list(step["agents_paths"], field_name=f"agents_paths for {step_id}")

    if "justification" in step and (
        not isinstance(step["justification"], str) or not step["justification"].strip()
    ):
        raise ValueError(f"justification must be a non-empty string for {step_id}")

    for optional_list_name in (
        "files_read_first",
        "interfaces_to_preserve",
        "avoid_touching",
        "verification_targets",
        "risk_flags",
        "blast_radius",
        "decision_ids",
        "depends_on",
        "file_ownership",
        "rollback_notes",
        "operational_watchpoints",
    ):
        if optional_list_name in step:
            _ensure_string_list(step[optional_list_name], field_name=f"{optional_list_name} for {step_id}")
    if "wave" in step and not _is_positive_int(step["wave"]):
        raise ValueError(f"wave must be a positive integer for {step_id}")

    return step_id, set(requirement_ids)


def infer_agents_paths(context_items: list[str]) -> list[str]:
    candidates: list[str] = []
    for item in context_items:
        value = item.strip()
        if not _looks_like_repo_path(value):
            continue
        path = Path(value.rstrip("/"))
        directory = path if value.endswith("/") or path.suffix == "" else path.parent
        current = ROOT_DIR / directory
        parents = [ROOT_DIR]
        parents.extend(parent for parent in current.parents if ROOT_DIR in parent.parents or parent == ROOT_DIR)
        if current.is_dir() or not current.suffix:
            parents.insert(1, current)
        for parent in sorted(set(parents), key=lambda p: len(p.parts)):
            agents_file = parent / "AGENTS.md"
            if agents_file.exists():
                candidates.append(str(agents_file.relative_to(ROOT_DIR)))
    if (ROOT_DIR / "AGENTS.md").exists():
        candidates.append("AGENTS.md")
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _looks_like_repo_path(value: str) -> bool:
    if not value or any(char.isspace() for char in value):
        return False
    return "/" in value or value.endswith((".py", ".md", ".json", ".yaml", ".yml", ".toml", ".sh"))


def _normalize_state_compat(state: Any, path: Path) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ValueError("workflow state must be a JSON object")

    normalized = dict(state)
    state_root = path.resolve().parent
    normalized.setdefault("uat_artifact_path", str(state_root / "uat.json"))
    normalized.setdefault("metrics_dir", str(state_root / "metrics"))
    normalized.setdefault("escalation", None)
    return normalized


def _ensure_string_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} must contain non-empty strings")
        normalized.append(item.strip())
    return normalized


def _default_commit_message(title: str, *, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = slug or f"workflow-step-{index}"
    return f"feature: {slug}"


def current_step(state: dict[str, Any]) -> dict[str, Any]:
    for step in state["steps"]:
        if step["id"] == state["current_step_id"]:
            return step
    raise ValueError(f"current step not found: {state['current_step_id']}")


def step_index(state: dict[str, Any], step_id: str) -> int:
    for index, step in enumerate(state["steps"]):
        if step["id"] == step_id:
            return index
    raise ValueError(f"step not found: {step_id}")


def evaluate_pre_review_sensors(
    state: dict[str, Any],
    *,
    step: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_state(state)
    step = step or current_step(state)
    verification_targets = list(step.get("verification_targets", []))
    failures: list[dict[str, Any]] = []

    if step["id"] != state["current_step_id"]:
        failures.append(
            _build_sensor_failure(
                code="review_required",
                step=step,
                summary=(
                    f"only the current step `{state['current_step_id']}` can advance to review_pending; "
                    f"got `{step['id']}`"
                ),
                sensor="current_step",
                details={
                    "current_step_id": state["current_step_id"],
                    "requested_step_id": step["id"],
                },
            )
        )

    if step["status"] not in REVIEW_PENDING_ENTRY_STATUSES:
        failures.append(
            _build_sensor_failure(
                code="review_required",
                step=step,
                summary=(
                    f"step `{step['id']}` cannot move to review_pending from `{step['status']}`; "
                    "expected implementing or fix_pending"
                ),
                sensor="status_path",
                details={
                    "current_status": step["status"],
                    "allowed_statuses": sorted(REVIEW_PENDING_ENTRY_STATUSES - {"review_pending"}),
                },
            )
        )

    if not step["verify_cmds"]:
        failures.append(
            _build_sensor_failure(
                code="verification_missing",
                step=step,
                summary="current step has no verification commands configured before review",
                sensor="verify_cmds",
                details={
                    "done_when": list(step["done_when"]),
                    "verification_targets": verification_targets,
                },
            )
        )
    else:
        command_targets = _extract_verify_targets(step["verify_cmds"])
        missing_targets = [
            target
            for target in verification_targets
            if not _path_is_covered_by_any(target, command_targets)
        ]
        if missing_targets:
            failures.append(
                _build_sensor_failure(
                    code="verification_missing",
                    step=step,
                    summary=(
                        "verification commands do not structurally cover every configured verification target"
                    ),
                    sensor="verification_targets",
                    details={
                        "verification_targets": verification_targets,
                        "command_targets": command_targets,
                        "missing_targets": missing_targets,
                        "done_when": list(step["done_when"]),
                    },
                )
            )

    ownership_paths = list(step.get("file_ownership", []))
    if ownership_paths and verification_targets:
        uncovered_targets = [
            target
            for target in verification_targets
            if not _path_is_covered_by_any(target, ownership_paths)
        ]
        if uncovered_targets:
            failures.append(
                _build_sensor_failure(
                    code="ownership_mismatch",
                    step=step,
                    summary="verification targets fall outside the current step file ownership",
                    sensor="file_ownership",
                    details={
                        "file_ownership": ownership_paths,
                        "verification_targets": verification_targets,
                        "uncovered_targets": uncovered_targets,
                    },
                )
            )

    required_agents_paths = infer_agents_paths(
        list(step["context"]) + verification_targets + ownership_paths
    )
    missing_agents_paths = [
        path for path in required_agents_paths if path not in step["agents_paths"]
    ]
    if missing_agents_paths:
        failures.append(
            _build_sensor_failure(
                code="agents_update_required",
                step=step,
                summary="configured AGENTS.md checks do not cover every relevant durable-guidance scope",
                sensor="agents_paths",
                details={
                    "configured_agents_paths": list(step["agents_paths"]),
                    "required_agents_paths": required_agents_paths,
                    "missing_agents_paths": missing_agents_paths,
                },
            )
        )

    return {
        "ok": not failures,
        "step_id": step["id"],
        "failures": failures,
    }


def find_execution_blocker(
    state: dict[str, Any],
    *,
    include_active_escalation: bool = True,
) -> dict[str, Any] | None:
    validate_state(state)
    if include_active_escalation and state["workflow_status"] == "execution_escalated":
        escalation = state["escalation"]
        if escalation is None:  # pragma: no cover - validate_state prevents this
            return None
        return dict(escalation)

    step = current_step(state)
    active_escalation = state.get("escalation")
    if (
        state["workflow_status"] == "execution_escalated"
        and not include_active_escalation
        and isinstance(active_escalation, dict)
        and active_escalation.get("code")
        in {
            "verification_missing",
            "verification_failed",
            "ownership_mismatch",
            "agents_update_required",
            "review_required",
        }
    ):
        sensor_result = evaluate_pre_review_sensors(state, step=step)
        if not sensor_result["ok"]:
            primary = dict(sensor_result["failures"][0])
            primary["details"] = sensor_result["failures"]
            return primary

    if step["status"] == "review_pending":
        sensor_result = evaluate_pre_review_sensors(state, step=step)
        if not sensor_result["ok"]:
            primary = dict(sensor_result["failures"][0])
            primary["details"] = sensor_result["failures"]
            return primary

    if step["status"] == "shipped" and state["workflow_status"] != "ship_pending":
        return {
            "code": "manual_override",
            "summary": (
                "workflow state is inconsistent after ship and requires explicit reconciliation before continuing"
            ),
            "blocking_step_id": step["id"],
            "details": {
                "workflow_status": state["workflow_status"],
                "step_status": step["status"],
            },
        }

    return None


def enter_execution_escalation(
    state: dict[str, Any],
    blocker: dict[str, Any],
    *,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], bool]:
    validate_state(state)
    if blocker.get("code") not in VALID_ESCALATION_CODES:
        raise ValueError(f"invalid escalation code: {blocker.get('code')}")

    now = timestamp or _utc_now_iso()
    existing = state.get("escalation")
    same_active_escalation = (
        state["workflow_status"] == "execution_escalated"
        and isinstance(existing, dict)
        and existing.get("code") == blocker.get("code")
        and existing.get("blocking_step_id") == blocker.get("blocking_step_id")
    )
    escalation = {
        "code": blocker["code"],
        "summary": str(blocker["summary"]),
        "blocking_step_id": blocker.get("blocking_step_id"),
        "details": blocker.get("details"),
        "first_triggered_at": existing["first_triggered_at"] if same_active_escalation else now,
        "last_triggered_at": now,
        "occurrence_count": (existing["occurrence_count"] + 1) if same_active_escalation else 1,
    }
    changed = state["workflow_status"] != "execution_escalated" or state.get("escalation") != escalation
    state["workflow_status"] = "execution_escalated"
    state["escalation"] = escalation
    return state, changed


def clear_execution_escalation(
    state: dict[str, Any],
    *,
    next_status: str = "active",
) -> tuple[dict[str, Any], dict[str, Any] | None, bool]:
    validate_state(state)
    if next_status == "execution_escalated":
        raise ValueError("next_status must clear execution escalation")
    previous = state.get("escalation")
    changed = state["workflow_status"] == "execution_escalated" or previous is not None
    state["workflow_status"] = next_status
    state["escalation"] = None
    return state, previous, changed


def next_stop_decision(state: dict[str, Any]) -> tuple[dict[str, Any], WorkflowDecision, bool]:
    validate_state(state)

    if state["workflow_status"] == "complete":
        return state, WorkflowDecision(action="noop"), False

    step = current_step(state)

    if state["workflow_status"] == "execution_escalated":
        return state, WorkflowDecision(action="escalate", prompt=_execution_escalation_prompt(state, step)), False

    if state["workflow_status"] == "replan_required":
        return state, WorkflowDecision(action="block", prompt=_replan_required_prompt(state, step)), False

    if state["workflow_status"] == "ship_pending":
        if step["status"] == "shipped":
            return state, WorkflowDecision(action="block", prompt=_ship_completion_prompt(state, step)), False
        return state, WorkflowDecision(action="block", prompt=_ship_prompt(state, step)), False

    blocker = find_execution_blocker(state, include_active_escalation=False)
    if blocker is not None:
        state, changed = enter_execution_escalation(state, blocker)
        step = current_step(state)
        return state, WorkflowDecision(action="escalate", prompt=_execution_escalation_prompt(state, step)), changed

    if state["workflow_status"] == "uat_pending":
        return state, WorkflowDecision(action="block", prompt=_uat_prompt(state, step)), False

    if state["workflow_status"] == "gap_closure_pending":
        if step["status"] == "committed":
            state["workflow_status"] = "uat_pending"
            return state, WorkflowDecision(action="block", prompt=_uat_prompt(state, step)), True
        if step["status"] == "review_pending":
            return state, WorkflowDecision(action="block", prompt=_review_prompt(state, step)), False
        if step["status"] == "fix_pending":
            return state, WorkflowDecision(action="block", prompt=_fix_prompt(state, step)), False
        if step["status"] == "commit_pending":
            return state, WorkflowDecision(action="block", prompt=_commit_prompt(state, step)), False
        if step["status"] == "pending":
            step["status"] = "implementing"
            return state, WorkflowDecision(action="block", prompt=_gap_closure_prompt(state, step)), True
        return state, WorkflowDecision(action="block", prompt=_gap_closure_prompt(state, step)), False

    if step["status"] == "pending":
        step["status"] = "implementing"
        return state, WorkflowDecision(action="block", prompt=_implementation_prompt(state, step, is_start=True)), True

    if step["status"] == "implementing":
        return state, WorkflowDecision(action="block", prompt=_implementation_prompt(state, step, is_start=False)), False

    if step["status"] == "review_pending":
        return state, WorkflowDecision(action="block", prompt=_review_prompt(state, step)), False

    if step["status"] == "fix_pending":
        return state, WorkflowDecision(action="block", prompt=_fix_prompt(state, step)), False

    if step["status"] == "commit_pending":
        return state, WorkflowDecision(action="block", prompt=_commit_prompt(state, step)), False

    if step["status"] == "committed":
        next_index = step_index(state, step["id"]) + 1
        if next_index < len(state["steps"]):
            next_step = state["steps"][next_index]
            state["current_step_id"] = next_step["id"]
            if next_step["status"] == "pending":
                next_step["status"] = "implementing"
            return state, WorkflowDecision(action="block", prompt=_implementation_prompt(state, next_step, is_start=True)), True
        if state["mode"] == "ship":
            state["workflow_status"] = "uat_pending"
            return state, WorkflowDecision(action="block", prompt=_uat_prompt(state, step)), True
        state["workflow_status"] = "complete"
        return state, WorkflowDecision(action="noop"), True

    raise ValueError(f"unsupported step status: {step['status']}")


def activation_prompt(state: dict[str, Any]) -> str:
    validate_state(state)
    step = current_step(state)
    return _implementation_prompt(state, step, is_start=True)


def _implementation_prompt(state: dict[str, Any], step: dict[str, Any], *, is_start: bool) -> str:
    intro = "Start the next execution step." if is_start else "Do not stop yet."
    verify_lines = _shell_commands(step["verify_cmds"])
    agents_lines = _bullets(step["agents_paths"] or ["AGENTS.md"])
    context_lines = _bullets(step["context"])
    constraints_lines = _bullets(step["constraints"])
    done_lines = _bullets(step["done_when"])
    justification_section = _optional_text_section("Justification", step.get("justification"))
    files_read_first_section = _optional_bullets("Files to read first", step.get("files_read_first", []))
    interfaces_section = _optional_bullets("Interfaces to preserve", step.get("interfaces_to_preserve", []))
    avoid_touching_section = _optional_bullets("Avoid touching", step.get("avoid_touching", []))
    verification_targets_section = _optional_bullets("Verification targets", step.get("verification_targets", []))
    risk_flags_section = _optional_bullets("Risk flags", step.get("risk_flags", []))
    blast_radius_section = _optional_bullets("Blast radius", step.get("blast_radius", []))
    decision_ids_section = _optional_bullets("Decision IDs", step.get("decision_ids", []))
    depends_on_section = _optional_bullets("Depends on", step.get("depends_on", []))
    wave_section = _optional_text_section("Wave", step.get("wave"))
    ownership_section = _optional_bullets("Owned files", step.get("file_ownership", []))
    rollback_section = _optional_bullets("Rollback notes", step.get("rollback_notes", []))
    watchpoints_section = _optional_bullets(
        "Operational watchpoints",
        step.get("operational_watchpoints", []),
    )
    return (
        f"{intro}\n\n"
        f"Current workflow: `{state['workflow_name']}`.\n"
        f"Current step: `{step['id']}` - {step['title']}\n\n"
        "Phase contract:\n"
        "- Development owns this step until it reaches `committed`.\n"
        "- Review is a blocking gate before commit.\n"
        "- Deployment does not begin until UAT advances the workflow to `ship_pending`.\n\n"
        f"Goal:\n{step['goal']}\n\n"
        f"{justification_section}"
        f"{wave_section}"
        f"{depends_on_section}"
        f"{ownership_section}"
        f"{files_read_first_section}"
        f"Context:\n{context_lines}\n\n"
        f"{interfaces_section}"
        f"{avoid_touching_section}"
        f"Constraints:\n{constraints_lines}\n\n"
        f"{verification_targets_section}"
        f"{risk_flags_section}"
        f"{blast_radius_section}"
        f"{rollback_section}"
        f"{watchpoints_section}"
        f"{decision_ids_section}"
        f"Done when:\n{done_lines}\n\n"
        f"Verification commands:\n{verify_lines}\n\n"
        f"AGENTS.md scope check:\n{agents_lines}\n\n"
        "Before you try to stop this turn, do all of the following:\n"
        "- Finish the step's implementation.\n"
        "- Run the step verification commands that apply.\n"
        "- Update the listed `AGENTS.md` files only if this step changed durable guidance.\n"
        "- Update `STATE.md` if this step changes active initiative status, latest decisions, release state, or unresolved risks.\n"
        f"- When the step is ready for review, run `{STATE_TOOL_COMMAND} set-step-status {step['id']} review_pending`.\n"
        "- Continue in the same thread until the step is ready for the review gate."
    )


def _review_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    return (
        "Run the review gate now.\n\n"
        f"Review only the current execution step `{step['id']}` - {step['title']} using `{state['review_path']}` and the same bug-focused standards as `/review`.\n"
        "This review stays inside the execution phase and blocks promotion from development work to commit.\n"
        "Treat the review as blocking:\n"
        "- Findings first, ordered by severity.\n"
        "- Focus on bugs, regressions, risky behavior, stale AGENTS guidance, and missing verification.\n"
        "- Do not pad with style-only feedback.\n\n"
        "If you find issues:\n"
        f"- Run `{STATE_TOOL_COMMAND} set-step-status {step['id']} fix_pending --review-summary \"<short summary>\"`.\n"
        "- Fix the issues, rerun the step verification, and then run "
        f"`{STATE_TOOL_COMMAND} set-step-status {step['id']} review_pending` before trying to stop again.\n\n"
        "If the review finds no new issues:\n"
        f"- Run `{STATE_TOOL_COMMAND} set-step-status {step['id']} commit_pending --review-summary \"review passed\"`.\n"
        "- Continue so the workflow can move to the commit phase."
    )


def _fix_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    verify_lines = _shell_commands(step["verify_cmds"])
    return (
        "The review gate still has open findings.\n\n"
        f"Current step: `{step['id']}` - {step['title']}\n"
        f"Last review summary: {step['review_summary'] or 'not recorded'}\n\n"
        "Fix the findings for this step only, rerun the relevant verification, and keep the diff scoped.\n\n"
        f"Verification commands:\n{verify_lines}\n\n"
        "When the fixes are ready for another review pass, run "
        f"`{STATE_TOOL_COMMAND} set-step-status {step['id']} review_pending` and continue."
    )


def _commit_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    return (
        "The current execution step passed verification and review.\n\n"
        f"Current step: `{step['id']}` - {step['title']}\n"
        f"Commit message: `{step['commit_message']}`\n\n"
        "Commit this step now:\n"
        "- Stage only the files that belong to this execution step.\n"
        "- Use the exact commit message from the workflow state.\n"
        "- Do not amend older commits unless the workflow explicitly requires it.\n\n"
        "After the commit succeeds, run "
        f"`{STATE_TOOL_COMMAND} set-step-status {step['id']} committed` and continue."
    )


def _uat_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    artifact_path = Path(state["uat_artifact_path"])
    artifact = load_uat_artifact(artifact_path)
    checklist_lines = "- uat artifact missing"
    summary_line = "Summary: none recorded"
    if artifact is not None:
        checklist_lines = "\n".join(
            f"- `{item['id']}` [{item['status']}] {item['title']}"
            for item in artifact["checklist"]
        )
        summary_line = f"Summary: {artifact['summary'] or 'none recorded'}"

    return (
        "Run the user-acceptance gate now.\n\n"
        f"Workflow: `{state['workflow_name']}`\n"
        f"Current step: `{step['id']}` - {step['title']}\n"
        f"UAT artifact: `{state['uat_artifact_path']}`\n"
        f"{summary_line}\n\n"
        "Checklist:\n"
        f"{checklist_lines}\n\n"
        "Evaluate the committed implementation against the approved plan, repo memory, and the checklist.\n"
        "Record only one outcome:\n"
        f"- Pass: `{STATE_TOOL_COMMAND} set-uat-status passed --summary \"<short summary>\"`\n"
        f"- Small fixable gap: `{STATE_TOOL_COMMAND} set-uat-status failed-gap --summary \"<short summary>\"`\n"
        f"- Scope or architecture mismatch that requires replanning: "
        f"`{STATE_TOOL_COMMAND} set-uat-status failed-replan --summary \"<short summary>\"`"
    )


def _gap_closure_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    artifact = load_uat_artifact(Path(state["uat_artifact_path"]))
    summary = artifact["summary"] if artifact is not None else None
    verify_lines = _shell_commands(step["verify_cmds"])
    return (
        "UAT found a fixable gap. Stay inside the current workflow and close it.\n\n"
        f"Workflow: `{state['workflow_name']}`\n"
        f"Current step: `{step['id']}` - {step['title']}\n"
        f"Current step status: `{step['status']}`\n"
        f"Latest UAT summary: {summary or 'not recorded'}\n\n"
        "Rules:\n"
        "- Fix only the gap identified by UAT.\n"
        "- Reuse the normal review and commit gates for the current step before rerunning UAT.\n"
        "- Do not start a new planning session for a fixable gap.\n\n"
        f"Verification commands:\n{verify_lines}\n\n"
        f"When the gap fix is ready for review, run `{STATE_TOOL_COMMAND} set-step-status {step['id']} review_pending`.\n"
        f"When the gap-fix commit lands, run `{STATE_TOOL_COMMAND} set-step-status {step['id']} committed` and resume to return to UAT."
    )


def _replan_required_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    artifact = load_uat_artifact(Path(state["uat_artifact_path"]))
    summary = artifact["summary"] if artifact is not None else None
    return (
        "This workflow is blocked in replan-required state and cannot ship.\n\n"
        f"Workflow: `{state['workflow_name']}`\n"
        f"Current step: `{step['id']}` - {step['title']}\n"
        f"UAT summary: {summary or 'not recorded'}\n\n"
        "Do not keep implementing on this execution workflow.\n"
        "Start a follow-up planning session that uses the UAT failure summary as the new input and treat the current workflow as terminal until that replan is approved."
    )


def _execution_escalation_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    escalation = state["escalation"] or {}
    details_lines = _escalation_details_lines(escalation.get("details"))
    return (
        "This workflow is escalated and cannot safely continue.\n\n"
        f"Workflow: `{state['workflow_name']}`\n"
        f"Workflow status: `{state['workflow_status']}`\n"
        f"Current step: `{step['id']}` - {step['title']}\n"
        f"Current step status: `{step['status']}`\n"
        f"Escalation category: `{escalation.get('code', 'unknown_blocker')}`\n"
        f"Reason: {escalation.get('summary', 'no summary recorded')}\n"
        f"First triggered: `{escalation.get('first_triggered_at', 'unknown')}`\n"
        f"Last triggered: `{escalation.get('last_triggered_at', 'unknown')}`\n"
        f"Occurrence count: `{escalation.get('occurrence_count', 0)}`\n\n"
        f"Details:\n{details_lines}\n\n"
        "Fix the blocking condition before continuing.\n"
        f"When the blocker is cleared, run `{STATE_TOOL_COMMAND} resolve-escalation` to return the workflow to "
        "active execution, then resume or run the next normal state transition."
    )


def _ship_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    review_flag = "true" if state["request_codex_review"] else "false"
    return (
        "UAT passed and the workflow is ready to ship. Finish the publish phase now.\n\n"
        f"Workflow: `{state['workflow_name']}`\n"
        f"Base branch: `{state['base_branch']}`\n"
        f"Use the `${state['ship_skill']}` skill.\n"
        f"Request `@codex review` after PR creation: `{review_flag}`\n\n"
        "Deployment scope for this workflow is limited to branch push, PR creation, optional `@codex review`, "
        "and workflow completion.\n\n"
        "Requirements:\n"
        "- Do not create an intermediate `PR_DESCRIPTION.md` file.\n"
        "- Generate the PR title and body in memory.\n"
        "- Prefer GitHub MCP for PR creation and PR comments; fall back to `gh` only if MCP is unavailable.\n"
        "- Push the current branch before creating the PR.\n\n"
        "When shipping succeeds:\n"
        f"- Run `{STATE_TOOL_COMMAND} set-step-status {step['id']} shipped`.\n"
        f"- Run `{STATE_TOOL_COMMAND} set-workflow-status complete`.\n"
        "- Report the PR URL and final status."
    )


def _ship_completion_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    return (
        "The publish work is already marked shipped, but the workflow is not closed yet.\n\n"
        f"Workflow: `{state['workflow_name']}`\n"
        f"Current step: `{step['id']}` - {step['title']}\n"
        "The current step is `shipped` and the workflow is still `ship_pending`.\n\n"
        "Finish the deployment phase now:\n"
        f"- Run `{STATE_TOOL_COMMAND} set-workflow-status complete`.\n"
        "- Report the PR URL and final status."
    )


def _shipped_state_reconciliation_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    return (
        "The workflow state is inconsistent and needs manual reconciliation.\n\n"
        f"Workflow: `{state['workflow_name']}`\n"
        f"Workflow status: `{state['workflow_status']}`\n"
        f"Current step: `{step['id']}` - {step['title']}\n"
        f"Current step status: `{step['status']}`\n\n"
        "Do not keep implementing. If publish really succeeded, reconcile the workflow state with explicit "
        "overrides or cancel the workflow before continuing."
    )


def _extract_verify_targets(commands: list[str]) -> list[str]:
    targets: list[str] = []
    for command in commands:
        for token in shlex.split(command):
            if token.startswith("-"):
                continue
            if _looks_like_repo_path(token):
                targets.append(token)
    return _unique_preserving_order(targets)


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _validate_escalation(escalation: Any) -> None:
    if escalation is None:
        return
    if not isinstance(escalation, dict):
        raise ValueError("escalation must be an object or null")
    required_fields = {
        "code",
        "summary",
        "blocking_step_id",
        "first_triggered_at",
        "last_triggered_at",
        "occurrence_count",
    }
    missing = sorted(required_fields - escalation.keys())
    if missing:
        raise ValueError(f"escalation missing required fields: {', '.join(missing)}")
    code = escalation["code"]
    if code not in VALID_ESCALATION_CODES:
        raise ValueError(f"invalid escalation code: {code}")
    summary = escalation["summary"]
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("escalation.summary must be a non-empty string")
    blocking_step_id = escalation["blocking_step_id"]
    if blocking_step_id is not None and (
        not isinstance(blocking_step_id, str) or not blocking_step_id.strip()
    ):
        raise ValueError("escalation.blocking_step_id must be a non-empty string or null")
    details = escalation.get("details")
    if details is not None and not isinstance(details, (dict, list)):
        raise ValueError("escalation.details must be an object, array, or null")
    for field_name in ("first_triggered_at", "last_triggered_at"):
        value = escalation[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"escalation.{field_name} must be a non-empty string")
    occurrence_count = escalation["occurrence_count"]
    if not isinstance(occurrence_count, int) or occurrence_count <= 0:
        raise ValueError("escalation.occurrence_count must be a positive integer")


def _build_sensor_failure(
    *,
    code: str,
    step: dict[str, Any],
    summary: str,
    sensor: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if code not in VALID_ESCALATION_CODES:
        raise ValueError(f"invalid escalation code: {code}")
    return {
        "code": code,
        "summary": summary,
        "blocking_step_id": step["id"],
        "details": {"sensor": sensor, **(details or {})},
    }


def _path_is_covered_by_any(path: str, candidates: list[str]) -> bool:
    return any(_path_is_covered(path, candidate) for candidate in candidates)


def _path_is_covered(path: str, candidate: str) -> bool:
    normalized_path = _normalize_coverage_path(path)
    normalized_candidate = _normalize_coverage_path(candidate)
    return normalized_path == normalized_candidate or normalized_path.startswith(normalized_candidate + "/")


def _normalize_coverage_path(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if "::" in normalized:
        node_path, _ = normalized.split("::", 1)
        if node_path.strip():
            normalized = node_path.strip().rstrip("/")
    return normalized


def _escalation_details_lines(details: Any) -> str:
    if details is None:
        return "- none recorded"
    if isinstance(details, list):
        lines: list[str] = []
        for item in details:
            if isinstance(item, dict):
                code = item.get("code", "unknown_blocker")
                summary = item.get("summary", "unknown blocker")
                sensor = ""
                if isinstance(item.get("details"), dict) and item["details"].get("sensor"):
                    sensor = f" ({item['details']['sensor']})"
                lines.append(f"- `{code}`{sensor}: {summary}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines) if lines else "- none recorded"
    if isinstance(details, dict):
        lines = [f"- {key}: {value}" for key, value in sorted(details.items())]
        return "\n".join(lines) if lines else "- none recorded"
    return f"- {details}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bullets(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _optional_bullets(title: str, items: list[str]) -> str:
    if not items:
        return ""
    return f"{title}:\n{_bullets(items)}\n\n"


def _optional_text_section(title: str, value: Any) -> str:
    if isinstance(value, int):
        return f"{title}:\n{value}\n\n"
    if not isinstance(value, str) or not value.strip():
        return ""
    return f"{title}:\n{value.strip()}\n\n"


def _shell_commands(commands: list[str]) -> str:
    if not commands:
        return "- none"
    return "\n".join(f"- `{command}`" for command in commands)
