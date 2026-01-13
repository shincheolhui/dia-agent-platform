# scripts/smoke.py
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _run_one(name: str, fn) -> bool:
    try:
        fn()
        print(f"PASS {name}")
        return True
    except AssertionError as e:
        print(f"FAIL {name}: {e}")
        return False
    except Exception as e:
        print(f"ERROR {name}: {type(e).__name__}: {e}")
        return False


def main() -> int:
    # lazy import to keep startup simple
    from core.tests.smoke_file_loader import smoke_file_loader
    from core.tests.smoke_context import smoke_context
    from core.tests.smoke_route import smoke_route
    from core.tests.smoke_meta import smoke_meta
    from core.tests.smoke_audit import smoke_audit


    ok = True
    ok &= _run_one("smoke_file_loader", smoke_file_loader)
    ok &= _run_one("smoke_context", smoke_context)
    ok &= _run_one("smoke_route", smoke_route)
    ok &= _run_one("smoke_meta", smoke_meta)
    ok &= _run_one("smoke_audit", smoke_audit)

    print("----")
    if ok:
        print("ALL PASS")
        return 0
    print("SOME FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
