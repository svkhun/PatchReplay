"""Opt-in fixed adversarial fixtures, always executed in Docker."""
import os
import pytest

from experiments.observer_boundary.host import demo

pytestmark = pytest.mark.skipif(not os.environ.get("PATCHREPLAY_TEST_IMAGE"),
                                reason="Requires immutable image and Linux Docker daemon")


def test_host_observer_and_known_legacy_weakness(tmp_path):
    report = demo(os.environ["PATCHREPLAY_TEST_IMAGE"], tmp_path / "observer")
    assert report["expected_outcomes_matched"], report
    assert len(report["observations"]) == 15
    assert report["legacy_demonstration"]["legacy_interpretation"] == "PASS"
    assert all(item["container_removed"] for item in report["observations"])
