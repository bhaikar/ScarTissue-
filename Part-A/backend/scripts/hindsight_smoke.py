"""Live Hindsight smoke test for disposable banks.

This script never deletes banks unless --cleanup is explicitly passed.
"""
from __future__ import annotations

import argparse
import inspect
import json
import random
import string
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import dotenv_values
from hindsight_client import Hindsight

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / "backend" / ".env"
OUTPUT_PATH = Path(__file__).resolve().parent / "_smoke_output.json"

REQUIRED_SIGNATURES = {
    name: inspect.signature(getattr(Hindsight, name))
    for name in ("retain", "recall", "create_bank", "list_memories", "delete_bank", "close")
}


def response_to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, list):
        return [response_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): response_to_jsonable(item) for key, item in value.items()}
    return value


def random_bank() -> str:
    return "scar-tissue-smoke-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-banks", nargs=2, metavar=("DEFAULT_BANK", "MISSION_BANK"))
    parser.add_argument("--cleanup", action="store_true")
    return parser.parse_args()


def failure_details(exc: Exception) -> tuple[int | None, str]:
    response = getattr(exc, "response", None)
    status = getattr(exc, "status_code", None) or getattr(response, "status_code", None)
    body = getattr(exc, "body", None)
    if body is None and response is not None:
        body = getattr(response, "text", None)
    if isinstance(body, dict):
        message = body.get("message") or body.get("error") or str(body)
    else:
        message = str(body) if body else "No response body message"
    return status, message


class StopForBillingError(RuntimeError):
    pass


def main() -> int:
    args = parse_args()
    env = dotenv_values(ENV_PATH)
    base_url = env.get("HINDSIGHT_API_URL")
    api_key = env.get("HINDSIGHT_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError("HINDSIGHT_API_URL or HINDSIGHT_API_KEY is missing from backend/.env")

    created_banks: list[str] = []
    if args.reuse_banks:
        default_bank, mission_bank = args.reuse_banks
    else:
        default_bank, mission_bank = random_bank(), random_bank()
        created_banks = [default_bank, mission_bank]

    client = Hindsight(base_url=base_url, api_key=api_key, timeout=30.0, max_attempts=3)
    results: dict[str, Any] = {
        "banks": {"default": default_bank, "mission": mission_bank},
        "created_banks": created_banks,
        "calls": [],
        "signatures": {name: str(signature) for name, signature in REQUIRED_SIGNATURES.items()},
    }
    print(f"default_bank={default_bank}")
    print(f"mission_bank={mission_bank}")

    def call(operation: str, fn: Callable[[], Any], *, record_return: bool = False) -> Any | None:
        started = time.perf_counter()
        try:
            value = fn()
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            entry: dict[str, Any] = {"operation": operation, "ok": True, "elapsed_ms": elapsed_ms}
            if record_return:
                entry["return"] = response_to_jsonable(value)
            results["calls"].append(entry)
            print(f"OK {operation} elapsed_ms={elapsed_ms}")
            return value
        except Exception as exc:  # Every SDK call is handled here.
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            status, message = failure_details(exc)
            results["calls"].append({
                "operation": operation,
                "ok": False,
                "elapsed_ms": elapsed_ms,
                "exception_type": type(exc).__name__,
                "http_status": status,
                "message": message,
            })
            print(f"FAIL {operation} {type(exc).__name__} status={status} message={message}")
            if status in {401, 402, 403}:
                raise StopForBillingError(
                    "Insufficient credits or authorization: add credits in Hindsight billing, then rerun"
                ) from exc
            return None

    def retain(bank: str, document: dict[str, Any], label: str) -> Any | None:
        return call(
            f"retain:{label}:{document['document_id']}",
            lambda: client.retain(
                bank_id=bank,
                content=document["content"],
                timestamp=datetime.now(timezone.utc).isoformat(),
                document_id=document["document_id"],
                metadata={"incident_id": document["document_id"].split(":")[1], "record_kind": "postmortem"},
                tags=document["tags"],
                retain_async=False,
                observation_scopes="per_tag",
            ),
            record_return=True,
        )

    def recall(bank: str, label: str, query: str, **kwargs: Any) -> Any | None:
        return call(
            f"recall:{label}",
            lambda: client.recall(bank, query=query, max_tokens=4096, **kwargs),
            record_return=True,
        )

    def create(bank: str, mission: bool) -> None:
        kwargs: dict[str, Any] = {"bank_id": bank}
        if mission:
            kwargs.update(
                mission="Preserve incident outcomes and applicability conditions.",
                retain_mission="Preserve failed, successful, and partial outcomes exactly and separately.",
                retain_custom_instructions="Never convert a failed remediation into a success; preserve worsened outcomes.",
            )
        call(f"create_bank:{bank}", lambda: client.create_bank(**kwargs))

    documents = [
        {"document_id": "smoke:INC-101:retry", "content": "Incident INC-101: retry amplification saturated the database. Increasing the DB connection pool FAILED and made DB CPU worse, rising from 62% to 94%. Disabling retries and rolling back SUCCEEDED. Applicability: 20 retries and no budget.", "tags": ["org:demo", "service:checkout", "env:prod"]},
        {"document_id": "smoke:INC-023:lock", "content": "Incident INC-023: lock contention followed a schema migration. Rollback of the migration SUCCEEDED.", "tags": ["org:demo", "service:catalog", "env:prod"]},
        {"document_id": "smoke:INC-029:certificate", "content": "Incident INC-029: certificate expiry caused TLS failures and timeouts. Certificate renewal SUCCEEDED.", "tags": ["org:demo", "service:identity", "env:prod"]},
    ]
    query = "INC-101 payment requests increased and database saturation after retry amplification"

    def poll(bank: str, label: str) -> list[Any]:
        started = time.perf_counter()
        facts: list[Any] = []
        attempts = 0
        while time.perf_counter() - started < 60:
            attempts += 1
            value = recall(bank, f"{label}:attempt_{attempts}", query, include_source_facts=True)
            if value is not None:
                raw = response_to_jsonable(value)
                facts = raw.get("results", raw.get("facts", [])) if isinstance(raw, dict) else []
                if facts:
                    break
            time.sleep(2)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        results.setdefault("polls", {})[label] = {"attempts": attempts, "until_facts_ms": elapsed_ms, "facts": facts}
        print(f"POLL {label} attempts={attempts} until_facts_ms={elapsed_ms} facts={len(facts)}")
        return facts

    try:
        create(default_bank, False)
        create(mission_bank, True)
        for document in documents:
            response = retain(default_bank, document, "default")
            if response is not None:
                print("RAW_RETAIN_RETURN", json.dumps(response_to_jsonable(response), sort_keys=True, default=str))
        retry = documents[0]
        retain(default_bank, retry, "duplicate_same_content")
        retain(default_bank, {**retry, "content": retry["content"] + " Changed-content re-retain marker."}, "duplicate_changed_content")
        listing = call("list_memories:retry-document", lambda: client.list_memories(default_bank, document_id=retry["document_id"], limit=100), record_return=True)
        results["duplicate_test"] = response_to_jsonable(listing)
        retain(default_bank, {**retry, "tags": ["org:demo", "service:payments", "env:prod"]}, "payments")
        facts = poll(default_bank, "inc101")
        failed, unqualified = [], []
        print("INC101_FACTS")
        for fact in facts:
            text = str(fact.get("text", "")) if isinstance(fact, dict) else str(fact)
            print(json.dumps({"type": fact.get("type") if isinstance(fact, dict) else None, "document_id": fact.get("document_id") if isinstance(fact, dict) else None, "text": text}, ensure_ascii=False))
            lower = text.lower()
            if ("pool" in lower or "increase" in lower) and any(word in lower for word in ("failed", "worse", "worsened")):
                failed.append(text)
            elif "pool" in lower or "increase" in lower:
                unqualified.append(text)
        results["negation_test"] = {"failed_evidence": failed, "pool_evidence_without_failure": unqualified}
        print("NEGATION_REASONING", json.dumps(results["negation_test"], ensure_ascii=False))
        for tags, match, label in [(["org:demo", "service:checkout"], "any_strict", "checkout_any_strict"), (["org:demo", "service:checkout", "env:prod"], "all_strict", "checkout_all_strict"), (["org:demo"], "all_strict", "org_only_all_strict")]:
            recall(default_bank, label, query, tags=tags, tags_match=match)
        for document in documents:
            retain(mission_bank, document, "mission")
        mission_facts = poll(mission_bank, "mission_inc101")
        results["mission_comparison"] = {"default": response_to_jsonable(recall(default_bank, "default_compare", query, include_source_facts=True)), "mission": response_to_jsonable(recall(mission_bank, "mission_compare", query, include_source_facts=True)), "mission_poll_facts": mission_facts}
    except StopForBillingError as exc:
        results["stopped"] = str(exc)
        print(str(exc))
        return_code = 2
    finally:
        results["timing_summary"] = [entry for entry in results["calls"] if entry["operation"].startswith(("retain:", "recall:"))]
        OUTPUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"saved_results={OUTPUT_PATH}")
        if args.cleanup and created_banks:
            for bank in created_banks:
                call(f"delete_bank:{bank}", lambda bank=bank: client.delete_bank(bank))
        client.close()
        print("client_closed=True")
    return locals().get("return_code", 0)


if __name__ == "__main__":
    sys.exit(main())
