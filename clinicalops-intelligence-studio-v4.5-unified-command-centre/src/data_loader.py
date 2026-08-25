import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def load_cases():
    return json.loads((ROOT / "data" / "synthetic_loop_cases.json").read_text(encoding="utf-8"))

def load_rules():
    return json.loads((ROOT / "data" / "loopguard_rules.json").read_text(encoding="utf-8"))["rules"]
