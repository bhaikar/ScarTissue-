from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def setup_function():
    client.post('/api/demo/reset')


def rule_payload(rule_id='CHK-RETRY-TEST'):
    return {
        'rule_id': rule_id,
        'name': 'Retry budget required',
        'expression': {'all': [
            {'field': 'retry_attempts', 'operator': 'gt', 'value': 5},
            {'field': 'retry_budget', 'operator': 'not_exists'},
        ]},
        'source_incident_ids': ['INC-017'],
    }


def test_rule_requires_approval_then_blocks_risky_and_passes_safe():
    proposed = client.post('/api/incidents/INC-017/preventive-rules', json=rule_payload()).json()
    risky = {'deployment_id': 'risk', 'service': 'checkout', 'retry_attempts': 20, 'retry_budget': None}
    safe = {'deployment_id': 'safe', 'service': 'checkout', 'retry_attempts': 3, 'retry_budget': 5}
    assert client.post('/api/deployments/evaluate', json={'deployment': risky}).json()['decision'] == 'PASS'
    approved = client.post(f"/api/preventive-rules/{proposed['rule_id']}/approval", json={'approver': 'engineer'})
    assert approved.json()['status'] == 'active'
    assert client.post('/api/deployments/evaluate', json={'deployment': risky}).json()['decision'] == 'BLOCKED'
    assert client.post('/api/deployments/evaluate', json={'deployment': safe}).json()['decision'] == 'PASS'


def test_resolution_is_idempotent_and_proposes_one_rule():
    body = {
        'idempotency_key': 'INC-101-resolution-test',
        'root_cause': 'Retry amplification after deployment',
        'action_taken': 'Disabled batch retries',
        'outcome': 'succeeded',
        'verification_evidence': ['Latency recovered'],
        'proposed_rule': {'all': [{'field': 'retry_attempts', 'operator': 'gt', 'value': 5}]},
    }
    first = client.post('/api/incidents/INC-101/resolution', json=body).json()
    second = client.post('/api/incidents/INC-101/resolution', json=body).json()
    assert first['learning_record_id'] == second['learning_record_id']
    records = client.get('/api/incidents/INC-101/learning-records').json()
    assert len(records) == 1


def test_reset_is_repeatable():
    first = client.post('/api/demo/reset').json()
    second = client.post('/api/demo/reset').json()
    assert first == second == {'status': 'reset'}
