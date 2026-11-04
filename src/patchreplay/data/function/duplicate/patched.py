import json, os, sys
r = json.loads(sys.argv[1])
answer = json.dumps({'protocol': 1, 'request_id': r['request_id'], 'value': 0})
print(answer, flush=True)
print(answer, flush=True)
os._exit(0)
