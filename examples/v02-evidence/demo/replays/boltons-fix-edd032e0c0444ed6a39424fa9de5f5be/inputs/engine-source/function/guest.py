"""Untrusted guest adapter: never decides whether an answer is correct."""
import json
import sys

request = json.loads(sys.argv[1])
sys.path.insert(0, "/input")
from candidate import clamp

value = clamp(*request["args"])
print(json.dumps({"protocol": 1, "request_id": request["request_id"], "value": value}, allow_nan=False))
