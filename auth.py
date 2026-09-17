"""兼容入口：实现位于 `.cursor/skills/xjtlu-owa-mail/scripts/xjtlu_owa_mail`。"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent / ".cursor" / "skills" / "xjtlu-owa-mail" / "scripts"
_s = str(_SCRIPTS)
if _s not in sys.path:
    sys.path.insert(0, _s)

from xjtlu_owa_mail.auth import (  # noqa: E402
    CACHE_DIR,
    OWA_CACHE_FILE,
    TGC_CACHE_FILE,
    get_authenticated_client,
)

__all__ = [
    "CACHE_DIR",
    "OWA_CACHE_FILE",
    "TGC_CACHE_FILE",
    "get_authenticated_client",
]
