"""Contract-shape compatibility; full runtime integrity is tested separately."""

from pathlib import Path

from patchreplay.contracts import CaseSpec
from patchreplay.engine import DATA
from patchreplay.integrity import read_json

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def test_case_schema_tracks_typed_contract():
    schema = read_json(SCHEMAS / "case.schema.json")
    assert set(schema["required"]) == set(CaseSpec.__dataclass_fields__)
    assert set(read_json(DATA / "cases" / "good.json")) == set(schema["required"])


def test_report_and_claim_shapes(demo_run, good_package):
    report = read_json(good_package / "report.json")
    schema = read_json(SCHEMAS / "report.schema.json")
    assert set(report) == set(schema["required"])
    assert set(report["checks"][0]) == set(schema["properties"]["checks"]["items"]["required"])
    assert set(report["steps"][0]) == set(schema["properties"]["steps"]["items"]["required"])
    root, _ = demo_run
    claim = read_json(root / "claim-suite-supported.json")
    assert set(claim) == set(read_json(SCHEMAS / "claim.schema.json")["required"])
