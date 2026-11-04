"""Reviewed, inert-host fixtures. These strings execute only in Docker."""

SOURCES = {
    "buggy": "def clamp(value, lower, upper):\n    return min(value, upper)\n",
    "correct": "def clamp(value, lower, upper):\n    return max(lower, min(value, upper))\n",
    # Deliberately writes a valid-looking pytest observation without running tests.
    # The legacy demonstration supplies evaluator metadata; the host oracle does not.
    "forge_records": '''import json, os
from pathlib import Path
contract = Path('/input/evaluator/contract.json')
nodes = json.loads(contract.read_text())['bug'] if contract.exists() else ['forged::test']
records = [{'node': node, 'when': when, 'outcome': 'passed', 'exception': None}
           for node in nodes for when in ['setup', 'call', 'teardown']]
Path('/work/records.json').write_text(json.dumps({'exit_code': 0, 'records': records}))
os._exit(0)
''',
    "forge_status": '''import json, os, sys
r = json.loads(sys.argv[1])
print(json.dumps({'protocol': 1, 'request_id': r['request_id'], 'value': 999,
                  'status': 'PASS'}), flush=True)
os._exit(0)
''',
    "duplicate": '''import json, os, sys
r = json.loads(sys.argv[1])
answer = json.dumps({'protocol': 1, 'request_id': r['request_id'], 'value': 0})
print(answer, flush=True)
print(answer, flush=True)
os._exit(0)
''',
    "wrong_round": '''import json, os
print(json.dumps({'protocol': 1, 'request_id': 'previous-round', 'value': 0}), flush=True)
os._exit(0)
''',
    "disconnect": "import os\nos._exit(0)\n",
    "timeout": "import time\ntime.sleep(60)\n",
    "flood": "import os\nwhile True:\n    os.write(1, b'x' * 4096)\n",
}

# Only the host reads the oracle. Each entry is (id, positional arguments, expected).
PROBES = (
    ("negative-lower", (-2, 0, 10), 0),
    ("nonzero-lower", (1, 5, 10), 5),
    ("in-range", (4, 0, 10), 4),
    ("upper", (12, 0, 10), 10),
)
