from app.contracts import MemoryMode
from app.services.diagnosis_service import FakeDiagnosisService, FakeMemoryService, load_incidents


def test_insufficient_evidence_is_low_confidence():
    incident = next(item for item in load_incidents() if item.incident_id == 'INC-102')
    result = FakeDiagnosisService(FakeMemoryService()).diagnose(incident, MemoryMode.off)
    assert result.output.confidence == 'low'
    assert result.output.missing_evidence


def test_memory_on_references_core_precedents():
    incident = next(item for item in load_incidents() if item.incident_id == 'INC-101')
    result = FakeDiagnosisService(FakeMemoryService()).diagnose(incident, MemoryMode.on)
    assert {'INC-017', 'INC-024'}.issubset(set(result.source_incident_ids))
    assert result.output.approaches_to_avoid
