import hashlib
import json
import time
from pathlib import Path

GENESIS = "0" * 64


class AuditLog:
    """Append-only, hash-chained. Each record commits to the previous hash, so a
    record cannot be altered after the fact without breaking the chain."""

    def __init__(self, path="audit.jsonl"):
        self.path = Path(path)
        self.path.touch(exist_ok=True)

    def _last_hash(self):
        last = None
        with self.path.open() as f:
            for line in f:
                if line.strip():
                    last = line
        if not last:
            return GENESIS
        return json.loads(last)["hash"]

    def append(self, record, policy_version="v1"):
        prev = self._last_hash()
        body = {
            "ts": time.time(),
            "policy_version": policy_version,
            "prev": prev,
            "record": record,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True).encode()
        ).hexdigest()
        body["hash"] = digest
        with self.path.open("a") as f:
            f.write(json.dumps(body) + "\n")
        return digest

    def verify(self):
        prev = GENESIS
        with self.path.open() as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry["prev"] != prev:
                    return False, i
                body = {k: entry[k] for k in ("ts", "policy_version", "prev", "record")}
                if hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != entry["hash"]:
                    return False, i
                prev = entry["hash"]
        return True, None
