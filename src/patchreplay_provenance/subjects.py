"""Extract explicit identity bindings without executing any evidence content."""
import re

from patchreplay.integrity import identity, read_json, verify_package
from patchreplay.claims import validate_report


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def observer(root):
    report = read_json(root / "results.json")
    if type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        raise ValueError("Unsupported observer report")
    if report.get("policy") != "experimental-host-oracle-v1":
        raise ValueError("Unsupported observer policy")
    engine = report["engine_files"]
    if not isinstance(engine, dict) or not engine or not all(sha(v) for v in engine.values()):
        raise ValueError("Invalid observer engine identities")
    if report["experiment_sha256"] != identity(engine):
        raise ValueError("Observer engine identity mismatch")
    rows = report["observations"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError("Invalid observer scope")
    sources, oracle, requests, images, cases = {}, [], set(), set(), set()
    for row in rows:
        request = row["request"]
        request_id = request["request_id"]
        if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id) or request_id in requests:
            raise ValueError("Missing, invalid or duplicated observer request ID")
        requests.add(request_id)
        fixture, probe = row["fixture"], row["probe"]
        if not all(isinstance(v, str) and re.fullmatch(r"[a-z0-9_-]{1,80}", v) for v in (fixture, probe)):
            raise ValueError("Invalid observer case identity")
        if (fixture, probe) in cases:
            raise ValueError("Duplicate observer case")
        cases.add((fixture, probe))
        if row["policy"] != report["policy"] or type(request["protocol"]) is not int or request["protocol"] != 1:
            raise ValueError("Observer policy/protocol mismatch")
        args = request["args"]
        if not isinstance(args, list) or len(args) != 3 or any(type(v) is not int for v in args) or type(row["expected"]) is not int:
            raise ValueError("Invalid integer-function oracle")
        source = row["source_sha256"]
        if not sha(source) or (fixture in sources and sources[fixture] != source):
            raise ValueError("Conflicting source identities")
        sources[fixture] = source
        image = row["image"]
        if not isinstance(image, str) or not image.startswith("sha256:") or not sha(image[7:]):
            raise ValueError("Observer requires immutable image identity")
        images.add(image)
        oracle.append({"fixture": fixture, "probe": probe, "args": args, "expected": row["expected"]})
    if len(images) != 1:
        raise ValueError("Mixed observer images")
    image = next(iter(images))
    return "observer-" + identity(sorted(requests)), {
        "sources": sources, "patch_sha256": None, "evaluator_sha256": identity(oracle),
        "engine_sha256": report["experiment_sha256"], "image": image, "policy": report["policy"],
        "request_ids_sha256": identity(sorted(requests))}


def describe(root, kind):
    if kind == "host-function-v1":
        from patchreplay.function.evidence import verify
        report = verify(root)
        return report["run_id"], report["identities"]
    if kind == "observer-v1":
        return observer(root)
    if kind == "patchreplay-v1":
        report = verify_package(root)
        validate_report(root, report)
        environment = read_json(root / "inputs/environment.json")
        return report["run_id"], {**report["identities"], "policy": report["executor"],
                                   "image": environment.get("container", {}).get("image")}
    raise ValueError("Unsupported subject kind")
