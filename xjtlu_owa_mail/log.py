"""进度日志统一写到 stderr，保证 stdout 只有结果（CLI 输出 JSON 时不被污染）。"""

from __future__ import annotations

import os
import sys



def _quiet() -> bool:
    return os.environ.get("XJTLU_OWA_QUIET", "").lower() in {"1", "true", "yes"}


def log(message: str) -> None:
    if _quiet():
        return
    print(message, file=sys.stderr, flush=True)
