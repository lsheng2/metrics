"""Repo-owned acceptance scope, independent of caller evidence classifications."""
from pathlib import Path

from scripts.validation.project_full_stack_support import read_json
from scripts.validation.windows_qualification_inputs import QualificationError


PROFILES = ("functional", "full")
CENSUS_PATH = "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-coverage.json"
PERFORMANCE_TESTS = (
    "ai_host/tests/test_windows_baseline_equivalence.py",
    "scripts/tests/test_windows_host_qualification.py",
    "ai_host/tests/conformance_performance_cases.py",
)
CLAUSE_ASPECTS = {
    "B1-native-second-signal": ("functional",),
    "B3-incremental-timing": ("performance",),
    "B4-disconnect-leaks": ("functional",),
    "M5-capacity-return": ("functional",),
    "B5-stream-stop": ("functional",),
    "B6-page-assets": ("performance",),
    "B6-production-static": ("performance",),
    "B7-browser-parity": ("functional",),
    "cold-and-stalled-assets": ("functional",),
    "B9-saturation": ("functional", "performance"),
    "repeat-order-matrix": ("functional",),
    "exclusive-window": ("performance",),
    "source-and-cleanup": ("functional", "performance"),
}


def require_profile(profile: str) -> str:
    if profile not in PROFILES:
        raise QualificationError("explicit functional or full acceptance profile required")
    return profile


def validate_canonical_census(coverage: dict, repo: Path) -> None:
    canonical = read_json(repo / CENSUS_PATH)
    for key in ("task_groups", "clauses", "source_requirement_digests", "requirement_digest_policy"):
        if key not in canonical or coverage.get(key) != canonical[key]:
            raise QualificationError(f"coverage differs from repo-owned census: {key}")
    identities = [(row["task_id"], row["clause_id"]) for row in canonical["clauses"]]
    if len(identities) != len(set(identities)):
        raise QualificationError("duplicate canonical clause identity")
    for task_id, clause_id in identities:
        if task_id == "10.4" and clause_id not in CLAUSE_ASPECTS:
            raise QualificationError(f"clause lacks reviewed phase policy: {clause_id}")


def clause_evidence_keys(task_id: str, clause_id: str, *, profile: str) -> list[str]:
    require_profile(profile)
    key = f"clause:{task_id}:{clause_id}"
    if task_id != "10.4":
        return [key]
    if clause_id not in CLAUSE_ASPECTS:
        raise QualificationError(f"clause lacks reviewed phase policy: {clause_id}")
    return [
        f"{key}:{aspect}" for aspect in CLAUSE_ASPECTS[clause_id]
        if profile == "full" or aspect == "functional"
    ]


def functional_lane_exclusions(target: str) -> list[str]:
    # These modules run explicitly in the later performance lane, never as
    # incidental children of the broad functional module suites.
    return [path for path in PERFORMANCE_TESTS[:2] if path.startswith(target + "/")]
