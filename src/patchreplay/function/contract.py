"""Strict function contract and host decision rules; no candidate imports."""
from patchreplay.contracts import require_keys, sha
from patchreplay.integrity import IntegrityError, canonical, identity

KIND = "host-function-v1"
POLICY = {
    "id": "docker-host-function-v1", "protocol": 1, "interface": "candidate.clamp(int,int,int)->int",
    "max_integer": 2**53 - 1, "max_response_bytes": 4096,
    "container_per_request": True, "network": "none", "read_only": True,
    "uid_gid": "65534:65534", "memory_bytes": 268435456, "cpus": 1,
    "pids": 64, "scratch_bytes": 67108864, "capabilities": [], "no_new_privileges": True,
    "control_timeout_seconds": 15, "guest_inputs": ["candidate.py", "guest.py"],
}
CASE_KEYS = {"schema_version", "case_id", "source_sha256", "patch_sha256", "patched_sha256",
             "evaluator_sha256", "suite_id", "suite_sha256", "policy_sha256", "interface", "repeats", "timeout_seconds"}
LIMITATIONS = [
    "Registered synthetic function cases only; no arbitrary repository, command or patch intake.",
    "MATCH proves only the declared numeric response, not which internal implementation executed.",
    "Request IDs correlate responses; they are visible to the guest and do not authenticate it.",
    "The host oracle, engine, reviewed image, Docker daemon and kernel are trusted.",
    "No generic pytest isolation, container escape resistance or production readiness is established.",
    "Replay pins recorded software and policy identities, not hardware, host load, scheduling or randomness.",
    "Hashes check consistency; signatures authenticate an expected subject, not truthful observations or correct code.",
]


def equal(actual, expected, message):
    if canonical(actual) != canonical(expected):
        raise IntegrityError(message)


def parse_case(data):
    version = data.get("schema_version")
    require_keys(data, CASE_KEYS | ({"provenance_sha256"} if version == 2 else set()), "Function case")
    if type(version) is not int or version not in (1, 2):
        raise IntegrityError("Unsupported function case version")
    import re
    for key in ("case_id", "suite_id"):
        if not isinstance(data[key], str) or not re.fullmatch(r"[a-z0-9-]{1,80}", data[key]):
            raise IntegrityError("Invalid function case/suite ID")
    if any(not sha(v) for k, v in data.items() if k.endswith("_sha256")):
        raise IntegrityError("Invalid function identity")
    if data["interface"] != POLICY["interface"] or data["policy_sha256"] != identity(POLICY):
        raise IntegrityError("Unsupported callable interface or policy")
    if type(data["repeats"]) is not int or not 2 <= data["repeats"] <= 5:
        raise IntegrityError("Function cases require two to five repeats")
    if type(data["timeout_seconds"]) is not int or not 1 <= data["timeout_seconds"] <= 30:
        raise IntegrityError("Invalid function timeout")
    return data


def limitations(case):
    if case["schema_version"] == 1:
        return LIMITATIONS
    return ["Registered upstream function extracts with reviewed adapters; synthetic controls are labeled in provenance.",
            "Exception sentinels encode only the specific exception declared by the adapter on the declared domain.",
            *LIMITATIONS[1:]]


def parse_oracle(data):
    require_keys(data, {"schema_version", "rule", "probes"}, "Function oracle")
    equal(data["schema_version"], 1, "Unsupported oracle version")
    equal(data["rule"], "all-declared-baseline-mismatches-v1", "Unsupported oracle decision rule")
    probes = data["probes"]
    if not isinstance(probes, list) or not 2 <= len(probes) <= 20:
        raise IntegrityError("Invalid probe count")
    seen, groups = set(), set()
    for p in probes:
        require_keys(p, {"id", "group", "args", "expected", "baseline"}, "Probe")
        if not isinstance(p["id"], str) or p["id"] in seen or not p["id"]:
            raise IntegrityError("Duplicate/invalid probe ID")
        seen.add(p["id"])
        if p["group"] not in {"bug", "regression"}:
            raise IntegrityError("Invalid probe group")
        groups.add(p["group"])
        if not isinstance(p["args"], list) or len(p["args"]) != 3:
            raise IntegrityError("Expected three integer arguments")
        if any(type(v) is not int or abs(v) > POLICY["max_integer"] for v in [*p["args"], p["expected"], p["baseline"]]):
            raise IntegrityError("Oracle values must be bounded integers")
        if (p["baseline"] == p["expected"]) != (p["group"] == "regression"):
            raise IntegrityError("Bug probes require a declared wrong baseline; regressions require a passing baseline")
    equal(sorted(groups), ["bug", "regression"], "Both probe groups are required")
    return data


def schedule(case, oracle):
    return [(phase, attempt, p) for attempt in range(1, case["repeats"] + 1)
            for phase in ("before", "after") for p in oracle["probes"]]


def decide(rows, case, oracle, failure=None):
    if failure:
        return failure["kind"], "Evaluation stopped at " + failure["stage"] + ": " + failure["detail"]
    for outcome in ("INTEGRITY_ERROR", "INFRA_ERROR", "TIMEOUT", "EXECUTION_ERROR", "INVALID_RESPONSE"):
        if any(r["observation"]["outcome"] == outcome for r in rows):
            return outcome, "At least one declared observation returned " + outcome + "."
    expected = [(phase, attempt, p["id"]) for phase, attempt, p in schedule(case, oracle)]
    actual = [(r["phase"], r["attempt"], r["probe_id"]) for r in rows]
    if actual != expected:
        return "INVALID_RESPONSE", "Required observations are missing, duplicated or out of order."
    by_probe = {(phase, p["id"]): [r["observation"]["value"] for r in rows
                                  if r["phase"] == phase and r["probe_id"] == p["id"]]
                for phase in ("before", "after") for p in oracle["probes"]}
    if any(len(set(values)) != 1 for values in by_probe.values()):
        return "REPEAT_DISAGREEMENT", "Repeated numeric responses disagreed."
    if any(by_probe["before", p["id"]][0] != p["expected"] for p in oracle["probes"] if p["group"] == "regression"):
        return "BASELINE_REGRESSION_FAILED", "Baseline regression observations must all match."
    if any(by_probe["before", p["id"]][0] != p["baseline"] for p in oracle["probes"] if p["group"] == "bug"):
        return "BUG_NOT_REPRODUCED", "Not every bug probe returned its declared wrong baseline value."
    if any(by_probe["after", p["id"]][0] != p["expected"] for p in oracle["probes"] if p["group"] == "regression"):
        return "REGRESSION_DETECTED", "A previously passing regression observation changed."
    if any(by_probe["after", p["id"]][0] != p["expected"] for p in oracle["probes"] if p["group"] == "bug"):
        return "FIX_FAILED", "The correction is incomplete for the declared bug probes."
    return "VERIFIED_FOR_DECLARED_CHECKS", "Every declared bug reproduced; all patched bug and regression probes matched across repeats."
