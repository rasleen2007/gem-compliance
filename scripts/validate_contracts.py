"""Validate every file under contracts/ is parseable JSON with a valid draft-07 $schema.

Usage: python scripts/validate_contracts.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


def main() -> int:
    failures = 0
    for path in sorted(CONTRACTS.glob("*.schema.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data.get("$schema") == "http://json-schema.org/draft-07/schema#"
            print(f"OK  {path.name}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"ERR {path.name}: {exc}")
    print("---")
    if failures:
        print(f"{failures} contract file(s) failed validation")
        return 1
    print("All contracts valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())