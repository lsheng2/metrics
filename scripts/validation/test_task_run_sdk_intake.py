from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
import sys
import unittest
import warnings
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch


MANIFEST_SHA = "08f081745ce956df13474de15063ec66849aef7a0454b3f0bd8fb4c56ee9bbca"
WHEEL_SHA = "de223668e49dc9ed145f6ec3bc5084d453a5611cee5f4f41987dd70a4474179f"
DESIGN_SHA = "ff7899333c8ed8f0717b47fc7c1d6a6e5928db575a15553d2501045f123719da"
WHEEL_NAME = "ai_base_application_sdk-0.1.0a1-py3-none-any.whl"
PROFILE_KEY = "project-reporting.summary@review-1"
SCHEMA_BASE = "https://schemas.example.invalid/project-reporting/review-1/"
EXPECTED_CALLS = {
    "test_installed_package_is_independent": 0,
    "test_pack_identity_and_profile_hash_domains": 0,
    "test_submit_transport_failure_keeps_original_key": 1,
    "test_lookup_is_explicit_and_does_not_resubmit": 2,
    "test_wrong_store_is_rejected": 1,
    "test_unknown_contract_is_rejected": 1,
    "test_incomplete_success_is_not_accepted": 1,
    "test_redirect_is_not_followed": 1,
    "test_credentials_are_not_in_public_error": 1,
    "test_strict_model_output_and_local_binding": 0,
    "test_no_unqualified_feature_is_claimed": 0,
    "test_valid_submit_lookup_and_result_are_accepted": 3,
}
CALLS_BY_TEST: dict[str, list[tuple[str, str]]] = {}
NETWORK_ATTEMPTS: list[str] = []
CONTEXT: IntakeContext | None = None


@dataclass(frozen=True, slots=True)
class IntakeContext:
    work_root: Path
    pack_root: Path
    manifest: dict[str, Any]
    sdk_dir: Path
    sdk: ModuleType
    httpx: ModuleType
    jsonschema: ModuleType
    registry: Any
    packages: list[dict[str, str]]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def pack_file(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve(strict=True)
    require(candidate.is_relative_to(root), "Artifact path escaped its pack")
    require(candidate.is_file(), "Artifact is not a file")
    return candidate


def blocked_schema(uri: str) -> Any:
    raise ValueError("Unregistered schema retrieval is forbidden")


def load_context(pack_root: Path) -> IntakeContext:
    repository = Path(__file__).resolve().parents[2]
    lexical_root = Path(os.path.abspath(pack_root))
    require(lexical_root.is_relative_to(repository / ".tmp"), "Pack path is not in the local work area")
    root = lexical_root.resolve(strict=True)
    work = root.parent.parent
    require(root.name == "contract-pack" and root.parent.name == "artifacts", "Unexpected pack layout")
    require(work.is_relative_to(repository / ".tmp"), "Work root is outside the owned temporary area")
    environment = (work / "venv").resolve(strict=True)
    require(environment.is_relative_to(work), "Linked environment escaped its work root")
    require(Path(sys.prefix).resolve() == environment, "Use the owned C0 interpreter")
    preparation = read_json(work / "preparation.json")
    require(preparation["owner"] == "scrum_dashboard", "Unknown preparation owner")
    require(Path(preparation["workRoot"]).resolve() == work, "Preparation work-root mismatch")
    require(preparation["environmentReady"] is True, "Environment is not prepared")
    manifest_bytes = (root / "manifest.json").read_bytes()
    require(digest(manifest_bytes) == MANIFEST_SHA, "Manifest identity mismatch")
    manifest = json.loads(manifest_bytes)
    require(len(manifest["files"]) == 19, "Unexpected artifact count")
    for relative, expected in manifest["files"].items():
        require(digest(pack_file(root, relative).read_bytes()) == expected, "Pack content hash mismatch")
    wheel = work / "artifacts" / WHEEL_NAME
    require(digest(wheel.read_bytes()) == WHEEL_SHA, "Wheel identity mismatch")
    require(preparation["manifestSha256"] == MANIFEST_SHA, "Preparation manifest mismatch")
    require(preparation["wheelSha256"] == WHEEL_SHA, "Preparation wheel mismatch")
    spec = importlib.util.find_spec("ai_base_application_sdk")
    require(spec is not None and spec.origin is not None, "SDK is not installed")
    sdk_dir = Path(spec.origin).resolve().parent
    require(sdk_dir.is_relative_to(environment), "SDK resolved outside the owned environment")
    with zipfile.ZipFile(wheel) as archive:
        require(archive.testzip() is None, "Wheel CRC failure")
        for name in ("__init__.py", "client.py"):
            installed = (sdk_dir / name).resolve(strict=True)
            require(installed.is_relative_to(sdk_dir), "Linked SDK source escaped its package")
            require(archive.read("ai_base_application_sdk/" + name) == installed.read_bytes(),
                    "Installed SDK differs from the approved wheel")
    report = read_json(work / "pip-install-report.json")
    packages = []
    for item in report["install"]:
        name, version = item["metadata"]["name"], item["metadata"]["version"]
        package_hash = item["download_info"].get("archive_info", {}).get("hashes", {}).get("sha256")
        require(isinstance(package_hash, str) and len(package_hash) == 64, "Dependency hash is missing")
        require(importlib.metadata.version(name) == version, "Installed dependency version drifted")
        packages.append({"name": name, "version": version, "sha256": package_hash})
    require(packages != [], "Empty dependency record")
    sdk = importlib.import_module("ai_base_application_sdk")
    httpx = importlib.import_module("httpx")
    jsonschema = importlib.import_module("jsonschema")
    referencing = importlib.import_module("referencing")
    registry = referencing.Registry(retrieve=blocked_schema)
    for name in ("summary-review.schema.json", "strict-summary-input.schema.json",
                 "strict-summary-output.schema.json"):
        schema = read_json(pack_file(root, "fixtures/project-summary/" + name))
        registry = registry.with_resource(SCHEMA_BASE + name, referencing.Resource.from_contents(schema))
    return IntakeContext(work, root, manifest, sdk_dir, sdk, httpx, jsonschema, registry, packages)


def validate_schema(context: IntakeContext, relative: str, value: Any) -> None:
    schema = read_json(pack_file(context.pack_root, relative))
    validator = context.jsonschema.Draft202012Validator
    validator.check_schema(schema)
    validator(schema, registry=context.registry).validate(value)


def fixture_submit(context: IntakeContext) -> dict[str, Any]:
    selected = context.manifest["profiles"][PROFILE_KEY]
    content = pack_file(context.pack_root, selected["input"]).read_bytes().decode("utf-8")
    canonical = json.dumps(json.loads(content), sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    return {
        "clientRunKey": "intake-key", "scopeKey": "projects.alpha.stages.one",
        "profile": {"key": "project-reporting.summary", "revision": "review-1"},
        "input": {"mediaType": "application/json", "content": content,
                  "sha256": digest(content.encode("utf-8"))},
        "logicalInputHash": {"algorithm": "dashboard-json-review-1", "digest": digest(canonical)},
        "deadlineAt": "2030-01-01T00:01:00.000Z",
        "limits": {"maxInputBytes": len(content.encode("utf-8")), "maxOutputBytes": 65536,
                   "maxInputTokens": None, "maxOutputTokens": None},
        "minimumResultRetentionSeconds": 60,
    }


def fixture_responses(context: IntakeContext, request: dict[str, Any]) -> tuple[dict, dict]:
    selected = context.manifest["profiles"][PROFILE_KEY]
    content = pack_file(context.pack_root, selected["output"]).read_bytes().decode("utf-8")
    output_hash = digest(content.encode("utf-8"))
    receipt = {
        "revision": 1, "executionMode": "synthetic", "backendId": "fixture",
        "modelName": None, "qualificationRef": None,
        "inputTokens": {"value": None, "certainty": "unknown"},
        "outputTokens": {"value": None, "certainty": "unknown"},
        "providerRequests": {"value": 0, "certainty": "known"},
        "cost": {"amountDecimal": None, "currency": None, "certainty": "unknown"},
    }
    common = {
        "contractVersion": "task-run/1", "runStoreId": "store-fixture",
        "runId": "run-fixture", "scopeKey": request["scopeKey"],
        "profile": dict(request["profile"], definitionSha256=selected["definitionSha256"]),
        "inputSha256": request["input"]["sha256"], "logicalInputHash": request["logicalInputHash"],
        "effectiveInputSha256": digest(b"synthetic compiled fixture"), "receipt": receipt,
    }
    result = dict(common, outputSchemaSha256=selected["outputSchemaSha256"],
                  content=content, mediaType="application/json", sha256=output_hash)
    snapshot = dict(
        common, sourceAppId="metrics-dashboard", clientRunKey=request["clientRunKey"],
        state="succeeded", lifecycleVersion=2, acceptedAt="2030-01-01T00:00:00.000Z",
        updatedAt="2030-01-01T00:00:30.000Z", terminalAt="2030-01-01T00:00:30.000Z",
        deadlineAt=request["deadlineAt"], grantRevision="fixture-grant-1",
        limitPolicyRevision="fixture-limits-1", acceptedLimits=request["limits"],
        resultRetentionSeconds=60, observationRetentionSeconds=120,
        observationExpiresAt="2030-01-01T00:02:30.000Z", unresolvedExposure=False,
        dispatch={"attemptCount": 1, "knowledge": "response_received", "remoteStop": "not_requested"},
        result={"availability": "available", "sha256": output_hash,
                "mediaType": "application/json", "expiresAt": "2030-01-01T00:01:30.000Z"},
        error=None,
    )
    return snapshot, result


class SdkIntakeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if CONTEXT is None:
            raise RuntimeError("Run this script with --pack-root and the C0 interpreter")
        cls.context = CONTEXT

    def setUp(self) -> None:
        self.submit_payload = fixture_submit(self.context)
        self.snapshot, self.result = fixture_responses(self.context, self.submit_payload)
        self.calls: list[tuple[str, str]] = []
        self.synthetic_token = "C0_SYNTHETIC_TOKEN_CANARY"

    async def asyncSetUp(self) -> None:
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyname_ex"):
            guard = patch(target, side_effect=self.forbid_network)
            guard.start()
            self.addCleanup(guard.stop)

    def tearDown(self) -> None:
        CALLS_BY_TEST[self._testMethodName] = self.calls.copy()

    def forbid_network(self, *args: Any, **kwargs: Any) -> None:
        NETWORK_ATTEMPTS.append(self._testMethodName)
        raise AssertionError("Real network is forbidden during C0")

    def client(self, handler: Any) -> Any:
        def record(request: Any) -> Any:
            self.calls.append((request.method, request.url.path))
            return handler(request)

        return self.context.sdk.TaskRunClient(
            base_url="http://candidate.example.invalid", source_app_id="metrics-dashboard",
            credential_ref="fixture-ref", token=self.synthetic_token, run_store_id="store-fixture",
            transport=self.context.httpx.MockTransport(record),
        )

    def timeout(self, request: Any) -> Any:
        raise self.context.httpx.ReadTimeout("offline fixture", request=request)

    async def submit_error(self, handler: Any) -> Any:
        async with self.client(handler) as client:
            with self.assertRaises(self.context.sdk.TaskRunClientError) as caught:
                await client.submit(self.submit_payload)
        return caught.exception

    def test_installed_package_is_independent(self) -> None:
        self.assertTrue(self.context.sdk_dir.is_relative_to(self.context.work_root / "venv"))
        self.assertEqual(importlib.metadata.version("ai-base-application-sdk"), "0.1.0a1")
        self.assertFalse(any(name == "app" or name.startswith("app.") or name == "template_runtime"
                             or name.startswith("template_runtime.") for name in sys.modules))
        self.assertFalse(any("Report_creater_agent" in entry for entry in sys.path))

    def test_pack_identity_and_profile_hash_domains(self) -> None:
        manifest = self.context.manifest
        self.assertEqual(manifest["designSha256"], DESIGN_SHA)
        self.assertEqual(len(manifest["files"]), 19)
        for relative, expected in manifest["files"].items():
            self.assertEqual(digest(pack_file(self.context.pack_root, relative).read_bytes()), expected)
        for name, selected in manifest["profiles"].items():
            profile_path = Path(selected["profile"])
            schema = profile_path.parent / "output.schema.json"
            self.assertEqual(digest(pack_file(self.context.pack_root, selected["profile"]).read_bytes()),
                             selected["definitionSha256"], name)
            self.assertEqual(digest(pack_file(self.context.pack_root, schema.as_posix()).read_bytes()),
                             selected["outputSchemaSha256"], name)
        for name, expected in manifest["sourceFixtureHashes"].items():
            self.assertEqual(digest(pack_file(self.context.pack_root, "fixtures/project-summary/" + name).read_bytes()),
                             expected)

    async def test_submit_transport_failure_keeps_original_key(self) -> None:
        error = await self.submit_error(self.timeout)
        self.assertEqual((error.code, error.recovery, error.client_run_key),
                         ("transport_outcome_unknown", "query_by_client_key", "intake-key"))
        self.assertEqual(self.calls, [("POST", "/api/runs")])

    async def test_lookup_is_explicit_and_does_not_resubmit(self) -> None:
        envelope = {
            "contractVersion": "task-run/1",
            "error": {"code": "run_not_found", "message": "Fixture not found.", "requestId": "fixture",
                      "clientRunKey": "intake-key", "runId": None,
                      "recovery": "lookup_or_resubmit_same_key", "retryAfterMs": None},
        }
        validate_schema(self.context, "schemas/ErrorEnvelope.json", envelope)

        def respond(request: Any) -> Any:
            if request.method == "POST":
                return self.timeout(request)
            self.assertEqual(dict(request.url.params),
                             {"scopeKey": "projects.alpha.stages.one", "clientRunKey": "intake-key"})
            return self.context.httpx.Response(404, json=envelope)

        async with self.client(respond) as client:
            with self.assertRaises(self.context.sdk.TaskRunClientError):
                await client.submit(self.submit_payload)
            with self.assertRaises(self.context.sdk.TaskRunClientError) as caught:
                await client.get_by_client_key(self.submit_payload["scopeKey"], "intake-key")
        error = caught.exception
        self.assertEqual((error.code, error.status, error.client_run_key), ("run_not_found", 404, "intake-key"))
        self.assertEqual(self.calls, [("POST", "/api/runs"), ("GET", "/api/runs/by-client-key")])

    async def test_wrong_store_is_rejected(self) -> None:
        value = dict(self.snapshot, runStoreId="other-store")
        error = await self.submit_error(lambda request: self.context.httpx.Response(200, json=value))
        self.assertEqual((error.code, error.recovery), ("run_store_mismatch", "stop"))

    async def test_unknown_contract_is_rejected(self) -> None:
        value = dict(self.snapshot, contractVersion="task-run/unsupported")
        error = await self.submit_error(lambda request: self.context.httpx.Response(200, json=value))
        self.assertEqual((error.code, error.recovery), ("contract_unsupported", "stop"))

    async def test_incomplete_success_is_not_accepted(self) -> None:
        value = copy.deepcopy(self.snapshot)
        del value["state"]
        error = await self.submit_error(lambda request: self.context.httpx.Response(200, json=value))
        self.assertEqual((error.code, error.recovery), ("invalid_response", "stop"))

    async def test_redirect_is_not_followed(self) -> None:
        error = await self.submit_error(lambda request: self.context.httpx.Response(
            307, content=b"", headers={"Location": "http://other.example.invalid/redirected"}))
        self.assertEqual((error.code, error.recovery, error.status, error.client_run_key),
                         ("invalid_response", "query_by_client_key", 307, "intake-key"))
        self.assertEqual(self.calls, [("POST", "/api/runs")])

    async def test_credentials_are_not_in_public_error(self) -> None:
        def fail(request: Any) -> Any:
            raise self.context.httpx.ReadTimeout(self.synthetic_token, request=request)

        error = await self.submit_error(fail)
        self.assertEqual(str(error), "Task request failed: transport_outcome_unknown")
        self.assertFalse(self.synthetic_token in str(error), "Public error leaked sensitive fixture data")

    def test_strict_model_output_and_local_binding(self) -> None:
        fixture_root = "fixtures/project-summary/"
        full = read_json(pack_file(self.context.pack_root, fixture_root + "summary-golden.json"))
        raw = json.loads(self.result["content"])
        validate_schema(self.context, fixture_root + "strict-summary-input.schema.json", full["input"])
        validate_schema(self.context, fixture_root + "strict-summary-output.schema.json", raw)
        self.assertNotIn("input_hash", raw)
        self.assertEqual(digest(self.result["content"].encode("utf-8")), self.result["sha256"])
        bound = dict(raw, input_hash=self.submit_payload["logicalInputHash"]["digest"])
        self.assertEqual(bound, full["candidate"])
        with self.assertRaises(self.context.jsonschema.ValidationError):
            validate_schema(self.context, fixture_root + "strict-summary-output.schema.json", bound)

    def test_no_unqualified_feature_is_claimed(self) -> None:
        self.assertEqual(self.context.manifest["qualification"], "synthetic_only")
        self.assertEqual(self.context.manifest["operations"], ["submit", "get_by_client_key", "get_result"])
        self.assertEqual(set(self.context.manifest["notQualified"]),
                         {"provider_execution", "native_crash_recovery", "cancellation",
                          "unknown_reconciliation", "physical_gc"})

    async def test_valid_submit_lookup_and_result_are_accepted(self) -> None:
        for name, value in (("RunSubmit", self.submit_payload), ("RunSnapshot", self.snapshot),
                            ("RunResult", self.result)):
            validate_schema(self.context, f"schemas/{name}.json", value)

        def respond(request: Any) -> Any:
            if request.method == "POST" and request.url.path == "/api/runs":
                self.assertEqual(json.loads(request.content), self.submit_payload)
                return self.context.httpx.Response(201, json=self.snapshot)
            if request.method == "GET" and request.url.path == "/api/runs/by-client-key":
                return self.context.httpx.Response(200, json=self.snapshot)
            if request.method == "GET" and request.url.path == "/api/runs/run-fixture/result":
                return self.context.httpx.Response(200, json=self.result)
            raise AssertionError("Unexpected SDK operation")

        async with self.client(respond) as client:
            snapshot = await client.submit(self.submit_payload)
            replay = await client.get_by_client_key(self.submit_payload["scopeKey"], "intake-key")
            result = await client.get_result(self.submit_payload["scopeKey"], "run-fixture")
        self.assertEqual(snapshot, self.snapshot)
        self.assertEqual(replay, self.snapshot)
        self.assertEqual(result, self.result)
        self.assertEqual(self.calls, [("POST", "/api/runs"), ("GET", "/api/runs/by-client-key"),
                                     ("GET", "/api/runs/run-fixture/result")])


def main() -> int:
    global CONTEXT
    parser = argparse.ArgumentParser(description="Run isolated, synthetic-only task-run SDK intake checks.")
    parser.add_argument("--pack-root", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        CONTEXT = load_context(arguments.pack_root)
    except (ValueError, OSError, KeyError, ImportError, zipfile.BadZipFile):
        print(json.dumps({"status": "preflight_failed", "requestsSent": 0}), file=sys.stderr)
        return 2
    warnings.simplefilter("error", RuntimeWarning)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SdkIntakeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    counts = {name: len(calls) for name, calls in CALLS_BY_TEST.items()}
    passed = (result.wasSuccessful() and result.testsRun == 12 and not result.skipped
              and counts == EXPECTED_CALLS and not NETWORK_ATTEMPTS)
    receipt = {
        "schemaVersion": 1, "status": "passed" if passed else "failed",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "testsRun": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "methodCalls": CALLS_BY_TEST,
        "callCountsMatch": counts == EXPECTED_CALLS, "realNetworkAttempts": len(NETWORK_ATTEMPTS),
        "manifestSha256": MANIFEST_SHA, "wheelSha256": WHEEL_SHA,
        "scriptSha256": digest(Path(__file__).read_bytes()),
        "pythonVersion": sys.version.split()[0], "dependencies": CONTEXT.packages,
        "qualification": "installed_sdk_mock_transport_only", "providerQualified": False,
        "applicationAcceptanceTested": False, "nativeRecoveryTested": False,
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    receipt_path = CONTEXT.work_root / f"sdk-intake-result-{stamp}.json"
    with receipt_path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "testsRun": result.testsRun,
                      "callCountsMatch": receipt["callCountsMatch"],
                      "realNetworkAttempts": len(NETWORK_ATTEMPTS),
                      "receipt": str(receipt_path)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
