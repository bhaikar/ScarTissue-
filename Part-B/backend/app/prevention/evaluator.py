from __future__ import annotations

from typing import Any

from app.contracts import PreventiveRule

MISSING = object()
FIELD_PATHS: dict[str, tuple[str, ...]] = {
    "service": ("service",),
    "retry_attempts": ("retry_attempts",),
    "retry_budget": ("retry_budget",),
    "timeout_seconds": ("timeout_seconds",),
    "connection_pool_size": ("connection_pool_size",),
    "feature_flags.batch_retries": ("feature_flags", "batch_retries"),
}


def get_field(deployment: dict[str, Any], field: str) -> Any:
    value: Any = deployment
    for part in FIELD_PATHS[field]:
        if not isinstance(value, dict) or part not in value:
            return MISSING
        value = value[part]
    return value


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def evaluate_condition(condition: Any, deployment: dict[str, Any]) -> tuple[bool, str | None]:
    actual = get_field(deployment, condition.field)
    operator = condition.operator

    if operator == "exists":
        return actual is not MISSING and actual is not None, None
    if operator == "not_exists":
        return actual is MISSING or actual is None, None
    if actual is MISSING:
        return False, None

    expected = condition.value
    if operator == "eq":
        return actual == expected, None
    if operator == "neq":
        return actual != expected, None

    if not is_number(actual) or not is_number(expected):
        return False, f"needs review: numeric comparison requires numeric values for {condition.field}"
    if operator == "gt":
        return actual > expected, None
    if operator == "gte":
        return actual >= expected, None
    if operator == "lt":
        return actual < expected, None
    if operator == "lte":
        return actual <= expected, None
    return False, f"needs review: unsupported operator {operator}"


def render_condition(condition: Any, deployment: dict[str, Any]) -> str:
    actual = get_field(deployment, condition.field)
    if condition.operator == "not_exists":
        return f"{condition.field} is missing"
    if condition.operator == "exists":
        return f"{condition.field} exists"
    return f"{condition.field} is {actual!r}; required {condition.operator} {condition.value!r}"


def evaluate_deployment(deployment: dict[str, Any], rules: list[PreventiveRule]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []

    for rule in rules:
        if rule.status != "active":
            continue
        matches = True
        messages: list[str] = []
        for condition in rule.expression.all:
            matched, review = evaluate_condition(condition, deployment)
            if review:
                reviews.append({"rule_id": rule.rule_id, "message": review})
                matches = False
                break
            if not matched:
                matches = False
            else:
                messages.append(render_condition(condition, deployment))
        if matches:
            violations.append({
                "rule_id": rule.rule_id,
                "name": rule.name,
                "message": "; ".join(messages),
                "source_incident_ids": rule.source_incident_ids,
            })

    # Unknown or unsafe comparisons fail closed. Deployment must not proceed.
    decision = "BLOCKED" if violations or reviews else "PASS"
    return {
        "deployment_id": deployment.get("deployment_id", "unknown"),
        "decision": decision,
        "violations": violations,
        "needs_review": reviews,
    }
