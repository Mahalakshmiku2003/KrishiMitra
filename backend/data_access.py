import json, os

_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "disease_db.json")
with open(_DB_PATH) as f:
    _DB = json.load(f)

_DEFAULT = {"severity_thresholds": {"mild": 0.20, "moderate": 0.60}}

def get_db_entry(label):
    if label in _DB:
        return _DB[label]
    for key, val in _DB.items():
        if key.lower().strip() == label.lower().strip():
            return val
    return _DEFAULT