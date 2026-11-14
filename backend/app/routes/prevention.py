from fastapi import APIRouter, HTTPException
from sqlmodel import Session

from app.contracts import ApprovalRequest, DeploymentEvaluationRequest, PreventiveRule, RuleStatusRequest
from app.database import engine
from app.services.prevention_service import approve_rule, create_rule, evaluate, update_rule_status

router = APIRouter(prefix="/api", tags=["prevention"])


@router.post("/incidents/{incident_id}/preventive-rules")
def propose_rule(incident_id: str, rule: PreventiveRule):
    if incident_id not in rule.source_incident_ids:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Source incident ID is required"})
    with Session(engine) as session:
        return create_rule(session, rule)


@router.post("/preventive-rules/{rule_id}/approval")
def approve(rule_id: str, request: ApprovalRequest):
    with Session(engine) as session:
        try:
            return approve_rule(session, rule_id, request.approver)
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "RULE_NOT_FOUND", "message": "Rule not found"})
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": str(exc)})


@router.post("/preventive-rules/{rule_id}/status")
def change_status(rule_id: str, request: RuleStatusRequest):
    with Session(engine) as session:
        try:
            return update_rule_status(session, rule_id, request.status, request.actor)
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "RULE_NOT_FOUND", "message": "Rule not found"})
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": str(exc)})


@router.post("/preventive-rules/{rule_id}/backtest")
def backtest(rule_id: str):
    with Session(engine) as session:
        rules = __import__("app.services.prevention_service", fromlist=["list_rules"]).list_rules(session)
    rule = next((r for r in rules if r.rule_id == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail={"code": "RULE_NOT_FOUND", "message": "Rule not found"})
    return {"rule_id": rule_id, "would_block": [], "would_pass": [], "status": "not_run_without_deployment_fixture"}


@router.post("/deployments/evaluate")
def deployment(request: DeploymentEvaluationRequest):
    with Session(engine) as session:
        return evaluate(session, request.deployment)
