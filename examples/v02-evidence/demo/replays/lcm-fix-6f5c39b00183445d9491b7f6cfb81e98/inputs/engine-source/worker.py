"""Trusted subprocess entry point; executed with Python -I -B.

This is an instrumentation adapter, NOT a sandbox. No arbitrary user code is
supported by the local executor.
"""

import json
import os
from pathlib import Path
import sys


def main():
    source, evaluator, selection, output, attempt = sys.argv[1:]
    sys.path.insert(0, source)
    os.environ["PATCHREPLAY_ATTEMPT"] = attempt
    import pytest

    contract = json.loads((Path(evaluator) / "contract.json").read_text())
    nodes = contract[selection]
    records = []

    class Recorder:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self, item, call):
            result = yield
            report = result.get_result()
            records.append({"node": item.nodeid, "when": report.when, "outcome": report.outcome,
                            "exception": call.excinfo.type.__name__ if call.excinfo else None})

    args = ["-q", "--tb=short", "--color=no", "--assert=plain", "--noconftest", "-p", "no:cacheprovider",
            "-c", str(Path(evaluator) / "pytest.ini"), "--rootdir", evaluator,
            f"--junitxml={Path(output).with_suffix('.xml')}"]
    args.extend(str(Path(evaluator) / node) for node in nodes)
    code = int(pytest.main(args, plugins=[Recorder()]))
    Path(output).write_text(json.dumps({"exit_code": code, "records": records}, sort_keys=True), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

