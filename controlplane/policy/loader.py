import yaml
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parents[2] / "configs" / "policies"


class Policy:
    def __init__(self, raw: dict):
        self.raw = raw
        self.use_case = raw["use_case"]
        self.latency_budget_ms = raw["latency_budget_ms"]
        self.streaming_mode = raw["streaming_mode"]
        self.tiers = raw["tiers"]
        self.costs = raw["costs"]
        self.actions = raw["actions"]
        self.audit = raw["audit"]

    def band(self):
        return tuple(self.tiers["tier1"]["uncertainty_band"])

    def tier_enabled(self, n):
        return self.tiers.get(f"tier{n}", {}).get("enabled", False)

    def checks(self, n):
        return self.tiers.get(f"tier{n}", {}).get("checks", [])


def load_all(directory=POLICY_DIR):
    out = {}
    for p in Path(directory).glob("*.yaml"):
        raw = yaml.safe_load(p.read_text())
        out[raw["use_case"]] = Policy(raw)
    return out
