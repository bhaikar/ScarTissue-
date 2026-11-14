import pytest
from pydantic import ValidationError

from app.contracts import PreventiveRule, RuleCondition, RuleExpression
from app.prevention.evaluator import evaluate_deployment


def retry_rule(status="active"):
    return PreventiveRule(
        rule_id="CHK-RETRY-001",
        name="Unbounded retry amplification",
        expression=RuleExpression(all=[
            RuleCondition(field="retry_attempts", operator="gt", value=5),
            RuleCondition(field="retry_budget", operator="not_exists"),
        ]),
        source_incident_ids=["INC-017"],
        status=status,
    )


def test_risky_deployment_blocks():
    result = evaluate_deployment({"deployment_id": "deploy-901", "retry_attempts": 20, "retry_budget": None}, [retry_rule()])
    assert result["decision"] == "BLOCKED"
    assert result["violations"][0]["source_incident_ids"] == ["INC-017"]


def test_safe_deployment_passes():
    result = evaluate_deployment({"deployment_id": "safe", "retry_attempts": 3, "retry_budget": 5}, [retry_rule()])
    assert result["decision"] == "PASS"


def test_unapproved_rule_does_not_block():
    result = evaluate_deployment({"deployment_id": "deploy-901", "retry_attempts": 20}, [retry_rule("proposed")])
    assert result["decision"] == "PASS"


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        RuleCondition(field="secret", operator="eq", value="x")


def test_unknown_operator_rejected():
    with pytest.raises(ValidationError):
        RuleCondition(field="retry_attempts", operator="eval", value=1)


def test_bool_is_not_number():
    rule = PreventiveRule(
        rule_id="CHK-1", name="bad type",
        expression=RuleExpression(all=[RuleCondition(field="retry_attempts", operator="gt", value=5)]),
        source_incident_ids=["INC-1"], status="active",
    )
    result = evaluate_deployment({"deployment_id": "x", "retry_attempts": True}, [rule])
    assert result["decision"] == "BLOCKED"
    assert result["needs_review"]


def test_missing_field_operators():
    exists = RuleCondition(field="retry_budget", operator="exists")
    missing = RuleCondition(field="retry_budget", operator="not_exists")
    assert evaluate_deployment({"deployment_id": "x"}, [PreventiveRule(rule_id="a", name="a", expression=RuleExpression(all=[exists]), source_incident_ids=["I"], status="active")])["decision"] == "PASS"
    assert evaluate_deployment({"deployment_id": "x"}, [PreventiveRule(rule_id="b", name="b", expression=RuleExpression(all=[missing]), source_incident_ids=["I"], status="active")])["decision"] == "BLOCKED"
