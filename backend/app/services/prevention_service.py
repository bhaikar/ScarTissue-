from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.contracts import PreventiveRule, RuleExpression
from app.models.database import DeploymentEvaluationRecord, RuleRecord
from app.prevention.evaluator import evaluate_deployment


def create_rule(session: Session, rule: PreventiveRule) -> PreventiveRule:
    existing = session.get(RuleRecord, rule.rule_id)
    if existing:
        return PreventiveRule.model_validate(json.loads(existing.payload_json))
    session.add(RuleRecord(rule_id=rule.rule_id, payload_json=rule.model_dump_json(), status=rule.status))
    session.commit()
    return rule


def list_rules(session: Session, active_only: bool = False) -> list[PreventiveRule]:
    records = session.exec(select(RuleRecord)).all()
    return [PreventiveRule.model_validate(json.loads(r.payload_json)) for r in records if not active_only or r.status == "active"]


def approve_rule(session: Session, rule_id: str, approver: str) -> PreventiveRule:
    record = session.get(RuleRecord, rule_id)
    if not record:
        raise KeyError(rule_id)
    rule = PreventiveRule.model_validate(json.loads(record.payload_json))
    if rule.status != "proposed":
        raise ValueError("Rule is not proposed")
    rule.status = "active"
    rule.approved_by = approver
    rule.approved_at = datetime.now(timezone.utc).isoformat()
    record.payload_json = rule.model_dump_json()
    record.status = "active"
    record.approved_by = approver
    record.approved_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    return rule


def update_rule_status(session: Session, rule_id: str, status: str, actor: str) -> PreventiveRule:
    record = session.get(RuleRecord, rule_id)
    if not record:
        raise KeyError(rule_id)
    rule = PreventiveRule.model_validate(json.loads(record.payload_json))
    if rule.status != "active" or status != "disabled":
        raise ValueError("Only active rules can be disabled")
    rule.status = status
    record.status = status
    record.payload_json = rule.model_dump_json()
    session.add(record)
    session.commit()
    return rule


def evaluate(session: Session, deployment: dict) -> dict:
    result = evaluate_deployment(deployment, list_rules(session, active_only=True))
    session.add(DeploymentEvaluationRecord(
        id=uuid.uuid4().hex,
        deployment_id=str(result["deployment_id"]),
        decision=result["decision"],
        payload_json=json.dumps(result),
    ))
    session.commit()
    return result
