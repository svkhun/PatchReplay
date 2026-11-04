"""Versioned typed contracts. Input validation is deliberately strict."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
import re


class Status(str, Enum):
    VERIFIED = "VERIFIED_FOR_DECLARED_CHECKS"
    NOT_REPRODUCED = "BUG_NOT_REPRODUCED"
    FIX_FAILED = "FIX_FAILED"
    REGRESSION = "REGRESSION_DETECTED"
    INTEGRITY = "EVALUATION_INTEGRITY_FAILED"
    INFRA = "INFRA_ERROR"
    INCONCLUSIVE = "INCONCLUSIVE"


class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED_FOR_SCOPE"
    STALE = "STALE"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


def require_keys(data: dict, keys: set[str], name: str) -> None:
    if not isinstance(data, dict) or set(data) != keys:
        raise ValueError(f"{name} must contain exactly: {', '.join(sorted(keys))}")


def sha(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True)
class CaseSpec:
    schema_version: int
    case_id: str
    title: str
    source_id: str
    source_revision: str
    patch: str
    patch_sha256: str
    evaluator_id: str
    evaluator_sha256: str
    suite_id: str
    suite_sha256: str
    repeats: int
    timeout_seconds: float
    required_pytest: str

    @classmethod
    def parse(cls, data: dict) -> "CaseSpec":
        require_keys(data, set(cls.__dataclass_fields__), "Case")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported case schema")
        for key in ("case_id", "source_id", "evaluator_id", "suite_id"):
            if not isinstance(data[key], str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", data[key]):
                raise ValueError(f"Invalid {key}")
        for key in ("patch_sha256", "evaluator_sha256", "suite_sha256"):
            if not sha(data[key]):
                raise ValueError(f"Invalid {key}")
        if not isinstance(data["source_revision"], str) or not data["source_revision"].startswith("sha256:") or not sha(data["source_revision"][7:]):
            raise ValueError("Source revision must be sha256:<snapshot tree hash>")
        if type(data["repeats"]) is not int or not 1 <= data["repeats"] <= 5:
            raise ValueError("repeats must be an integer between 1 and 5")
        timeout = data["timeout_seconds"]
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0.05 <= timeout <= 60:
            raise ValueError("timeout_seconds must be finite and between 0.05 and 60")
        if not isinstance(data["required_pytest"], str) or not re.fullmatch(r"\d+\.\d+\.\d+", data["required_pytest"]):
            raise ValueError("required_pytest must be an exact version")
        for key in ("title", "patch"):
            if not isinstance(data[key], str) or not 1 <= len(data[key]) <= 300:
                raise ValueError(f"Invalid {key}")
        return cls(**data)

    def as_dict(self) -> dict:
        return asdict(self)


PHASES = ("before_bug", "before_regression", "after_bug", "after_regression")


def decide(checks: list[dict], repeats: int) -> tuple[Status, str]:
    if any(c["outcome"] == "INTEGRITY_ERROR" for c in checks):
        return Status.INTEGRITY, "Protected inputs changed during evaluation."
    if any(c["outcome"] == "INFRA_ERROR" for c in checks):
        return Status.INFRA, "The evaluator did not produce a complete, interpretable result."
    if any(c["outcome"] == "TIMEOUT" for c in checks):
        return Status.INCONCLUSIVE, "A declared time budget expired; this does not establish correctness."
    if len(checks) != repeats * len(PHASES):
        return Status.INFRA, "Required checks are missing."
    by_phase = {p: [c for c in checks if c["phase"] == p] for p in PHASES}
    if any(len(rows) != repeats or {c["attempt"] for c in rows} != set(range(1, repeats + 1)) for rows in by_phase.values()):
        return Status.INFRA, "Check attempts are missing or duplicated."
    for rows in by_phase.values():
        if len({c["signature"] for c in rows}) > 1:
            return Status.INCONCLUSIVE, "Repeated checks disagreed; the result is unstable."
    first = {p: rows[0] for p, rows in by_phase.items()}
    if first["before_bug"]["outcome"] == "PASS":
        return Status.NOT_REPRODUCED, "The declared bug examples already pass before this patch."
    if first["before_bug"]["outcome"] != "EXPECTED_FAILURE":
        return Status.INCONCLUSIVE, "Baseline failures did not match the approved assertion failures."
    if first["before_regression"]["outcome"] != "PASS":
        return Status.INCONCLUSIVE, "Regression checks do not have a clean baseline."
    if first["after_bug"]["outcome"] != "PASS":
        return Status.FIX_FAILED, "The patch does not pass every declared bug example."
    if first["after_regression"]["outcome"] != "PASS":
        return Status.REGRESSION, "Previously passing regression checks fail after the patch."
    return Status.VERIFIED, "The bug reproduced, then all declared bug and regression checks passed."

