from __future__ import annotations

from metrics_lib import append_metrics_event


def emit_execution_transition_metrics(
    state: dict,
    *,
    previous_status: str,
    source: str,
) -> None:
    if previous_status == state["workflow_status"]:
        return
    if state["workflow_status"] != "execution_escalated":
        return
    escalation = state.get("escalation")
    if not isinstance(escalation, dict):
        return

    if isinstance(escalation.get("details"), list):
        append_metrics_event(
            state["metrics_dir"],
            "deterministic_sensor_failed",
            details={
                "workflow_name": state["workflow_name"],
                "step_id": state["current_step_id"],
                "category": escalation["code"],
                "summary": escalation["summary"],
                "failure_count": len(escalation["details"]),
                "source": source,
            },
        )
    append_metrics_event(
        state["metrics_dir"],
        "execution_escalation_entered",
        details={
            "workflow_name": state["workflow_name"],
            "current_step_id": state["current_step_id"],
            "previous_status": previous_status,
            "workflow_status": state["workflow_status"],
            "category": escalation["code"],
            "summary": escalation["summary"],
            "occurrence_count": escalation["occurrence_count"],
        },
    )
