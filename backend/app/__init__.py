"""Package bootstrap. Adds the repo root to sys.path so `core_ai` is importable
no matter where uvicorn/pytest is launched (backend/ or repo root)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

__version__ = "0.1.0"