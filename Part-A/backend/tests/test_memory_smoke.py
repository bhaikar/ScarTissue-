from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "hindsight_smoke.py"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("hindsight_smoke_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeApiException(Exception):
    def __init__(self) -> None:
        super().__init__("payment required")
        self.status_code = 402
        self.body = {"message": "billing credits required"}
        self.response = type("Response", (), {"status_code": 402, "text": "billing credits required", "headers": {"Authorization": "secret"}})()


class FakeHindsight:
    instances: list["FakeHindsight"] = []

    def __init__(self, **kwargs):
        self.calls: list[str] = []
        self.closed = False
        type(self).instances.append(self)

    def create_bank(self, **kwargs):
        self.calls.append("create_bank")
        raise FakeApiException()

    def retain(self, **kwargs):
        self.calls.append("retain")
        raise AssertionError("retain must not run after the first 402")

    def recall(self, *args, **kwargs):
        self.calls.append("recall")
        raise AssertionError("recall must not run after the first 402")

    def close(self):
        self.calls.append("close")
        self.closed = True


def test_billing_failure_stops_without_polling_and_writes_results(tmp_path, monkeypatch, capsys):
    module = load_smoke_module()
    fake = FakeHindsight
    fake.instances.clear()
    output_path = tmp_path / "_smoke_output.json"

    monkeypatch.setattr(module, "dotenv_values", lambda path: {
        "HINDSIGHT_API_URL": "https://example.invalid",
        "HINDSIGHT_API_KEY": "not-a-real-key",
    })
    monkeypatch.setattr(module, "Hindsight", fake)
    monkeypatch.setattr(module, "OUTPUT_PATH", output_path)
    monkeypatch.setattr(module.time, "sleep", lambda _: (_ for _ in ()).throw(AssertionError("sleep must not run")))
    monkeypatch.setattr(sys, "argv", ["hindsight_smoke.py"])

    assert module.main() == 2

    instance = fake.instances[0]
    assert instance.calls == ["create_bank", "close"]
    assert instance.closed is True
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["stopped"].startswith("Insufficient credits")

    output = capsys.readouterr().out
    assert "status=402" in output
    assert "billing credits required" in output
    assert "Authorization" not in output
    assert "secret" not in output
    assert "recall" not in output
    assert "sleep" not in output
