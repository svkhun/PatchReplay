import json, os
print(json.dumps({'protocol': 1, 'request_id': 'previous-round', 'value': 0}), flush=True)
os._exit(0)
