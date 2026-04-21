from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = WORKFLOW_DIR / "state.json"
STATE_EXAMPLE_PATH = WORKFLOW_DIR / "state.example.json"
STATE_SCHEMA_PATH = WORKFLOW_DIR / "state.schema.json"
PLAN_SCHEMA_PATH = WORKFLOW_DIR / "plan.schema.json"
STATE_TOOL_COMMAND = "python3 scripts/workflow_state.py"
DEFAULT_REVIEW_PATH = "code_review.md"
DEFAULT_SHIP_SKILL = "ship"
DEFAULT_BASE_BRANCH = "origin/main"

VALID_WORKFLOW_STATUSES = {"active", "ship_pending", "complete"}
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


@dataclass(frozen=True)
class WorkflowDecision:
    action: str
    prompt: str | None = None


def load_state(path: Path = DEFAULT_STATE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
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
        "mode",
        "plan_path",
        "review_path",
        "ship_skill",
        "current_step_id",
        "base_branch",
        "request_codex_review",
        "steps",
    }
    missing = sorted(required_fields - state.keys())
    if missing:
        raise ValueError(f"workflow state missing required fields: {', '.join(missing)}")

    if state["version"] != 1:
        raise ValueError("workflow state version must be 1")
    if state["workflow_status"] not in VALID_WORKFLOW_STATUSES:
        raise ValueError(f"invalid workflow_status: {state['workflow_status']}")
    if state["mode"] not in VALID_MODES:
        raise ValueError(f"invalid mode: {state['mode']}")
    if not isinstance(state["request_codex_review"], bool):
        raise ValueError("request_codex_review must be a boolean")

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
        "mode": workflow_mode,
        "plan_path": plan_spec.get("plan_path", plan_path),
        "review_path": plan_spec.get("review_path", review_path),
        "ship_skill": plan_spec.get("ship_skill", ship_skill),
        "current_step_id": normalized_steps[0]["id"],
        "base_branch": plan_spec.get("base_branch", base_branch),
        "request_codex_review": bool(plan_spec.get("request_codex_review", request_codex_review)),
        "steps": normalized_steps,
    }


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

    return {
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
    ):
        if optional_list_name in step:
            _ensure_string_list(step[optional_list_name], field_name=f"{optional_list_name} for {step_id}")

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


def next_stop_decision(state: dict[str, Any]) -> tuple[dict[str, Any], WorkflowDecision, bool]:
    validate_state(state)

    if state["workflow_status"] == "complete":
        return state, WorkflowDecision(action="noop"), False

    step = current_step(state)

    if step["status"] == "shipped":
        state["workflow_status"] = "complete"
        return state, WorkflowDecision(action="noop"), True

    if state["workflow_status"] == "ship_pending":
        return state, WorkflowDecision(action="block", prompt=_ship_prompt(state, step)), False

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
            state["workflow_status"] = "ship_pending"
            return state, WorkflowDecision(action="block", prompt=_ship_prompt(state, step)), True
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
    return (
        f"{intro}\n\n"
        f"Current workflow: `{state['workflow_name']}`.\n"
        f"Current step: `{step['id']}` - {step['title']}\n\n"
        f"Goal:\n{step['goal']}\n\n"
        f"Context:\n{context_lines}\n\n"
        f"Constraints:\n{constraints_lines}\n\n"
        f"Done when:\n{done_lines}\n\n"
        f"Verification commands:\n{verify_lines}\n\n"
        f"AGENTS.md scope check:\n{agents_lines}\n\n"
        "Before you try to stop this turn, do all of the following:\n"
        "- Finish the step's implementation.\n"
        "- Run the step verification commands that apply.\n"
        "- Update the listed `AGENTS.md` files only if this step changed durable guidance.\n"
        f"- When the step is ready for review, run `{STATE_TOOL_COMMAND} set-step-status {step['id']} review_pending`.\n"
        "- Continue in the same thread until the step is ready for the review gate."
    )


def _review_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    return (
        "Run the review gate now.\n\n"
        f"Review only the current execution step `{step['id']}` - {step['title']} using `{state['review_path']}` and the same bug-focused standards as `/review`.\n"
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


def _ship_prompt(state: dict[str, Any], step: dict[str, Any]) -> str:
    review_flag = "true" if state["request_codex_review"] else "false"
    return (
        "The last execution step is committed. Finish the publish phase now.\n\n"
        f"Workflow: `{state['workflow_name']}`\n"
        f"Base branch: `{state['base_branch']}`\n"
        f"Use the `${state['ship_skill']}` skill.\n"
        f"Request `@codex review` after PR creation: `{review_flag}`\n\n"
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


def _bullets(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _shell_commands(commands: list[str]) -> str:
    if not commands:
        return "- none"
    return "\n".join(f"- `{command}`" for command in commands)
