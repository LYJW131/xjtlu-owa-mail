"""兼容入口：实现位于 skill 包内。"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent / ".cursor" / "skills" / "xjtlu-owa-mail" / "scripts"
_s = str(_SCRIPTS)
if _s not in sys.path:
    sys.path.insert(0, _s)

from xjtlu_owa_mail.owa_auth import (  # noqa: E402
    IE_UA,
    OWA_HOME,
    get_owa_session,
    login_owa,
)

__all__ = ["IE_UA", "OWA_HOME", "get_owa_session", "login_owa"]
