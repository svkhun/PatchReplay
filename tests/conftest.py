from pathlib import Path

import pytest

from patchreplay.demo import demo
from patchreplay.integrity import read_json


@pytest.fixture(scope="session")
def demo_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("demo")
    summary = demo(root, progress=lambda _: None)
    return root, summary


@pytest.fixture
def good_package(demo_run):
    root, summary = demo_run
    item = next(c for c in summary["cases"] if c["case_id"] == "good")
    return root / item["package"]
