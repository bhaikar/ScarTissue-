import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get('/api/health').json() == {'status': 'ok'}


def test_incidents_and_diagnosis():
    response = client.get('/api/incidents')
    assert response.status_code == 200
    assert any(item['incident_id'] == 'INC-101' for item in response.json())
    diagnosis = client.post('/api/incidents/INC-101/diagnoses', json={'mode': 'on'})
    assert diagnosis.status_code == 200
    body = diagnosis.json()
    assert body['output']['confidence'] == 'high'
    assert 'INC-017' in body['source_incident_ids']


def test_missing_incident():
    assert client.get('/api/incidents/nope').status_code == 404
