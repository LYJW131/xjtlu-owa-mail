"""兼容入口：UIM 登录委托给 xjtlu-uim-login（经 skill 包再导出）。"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent / ".cursor" / "skills" / "xjtlu-owa-mail" / "scripts"
_s = str(_SCRIPTS)
if _s not in sys.path:
    sys.path.insert(0, _s)

from xjtlu_owa_mail.uim_login import get_tgc_cookie, load_project_env  # noqa: E402

__all__ = ["get_tgc_cookie", "load_project_env"]


if __name__ == "__main__":
    print(get_tgc_cookie())
