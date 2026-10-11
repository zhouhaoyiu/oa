"""Compatibility entry point: local inbox only, no WeChat."""
from oa_app import run

if __name__ == "__main__":
    raise SystemExit(run())
