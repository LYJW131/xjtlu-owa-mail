"""仓库根演示入口：转发到 skill scripts/example.py。"""

from __future__ import annotations

import runpy
from pathlib import Path

_EXAMPLE = (
    Path(__file__).resolve().parent
    / ".cursor"
    / "skills"
    / "xjtlu-owa-mail"
    / "scripts"
    / "example.py"
)

if __name__ == "__main__":
    runpy.run_path(str(_EXAMPLE), run_name="__main__")
