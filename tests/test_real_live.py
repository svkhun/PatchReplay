"""Real Docker acceptance of pinned upstream extracts, controls, claims and replay."""
import os
import pytest
from patchreplay.function_demo import demo


@pytest.mark.skipif(not os.environ.get("PATCHREPLAY_TEST_IMAGE"), reason="Requires real Docker and pinned evaluator image")
def test_upstream_demo_and_claims(tmp_path):
    result = demo(os.environ["PATCHREPLAY_TEST_IMAGE"], tmp_path / "upstream-demo")
    assert result["expected_outcomes_matched"]
    assert len(result["cases"]) == 6 and len(result["replays"]) == 2
    assert result["claims"][0]["observed"]["numerator"] == 2
    assert result["claims"][0]["observed"]["denominator"] == 6
