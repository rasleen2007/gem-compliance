"""Adds the backend package dir to sys.path so `from app...` imports resolve
regardless of invocation directory. The app package also injects the repo root
for `core_ai` (see app/__init__.py)."""