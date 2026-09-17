#!/usr/bin/env python3
"""检查 skill / 库运行前置条件（不发起网络登录）。"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def main() -> int:
    errors = 0

    # Python version
    if sys.version_info >= (3, 12):
        _ok(f"Python {sys.version.split()[0]}")
    else:
        _fail(f"需要 Python 3.12+，当前 {sys.version.split()[0]}")
        errors += 1

    for mod in ("requests", "bs4", "dotenv", "xjtlu_uim_login"):
        if importlib.util.find_spec(mod if mod != "bs4" else "bs4") is not None:
            _ok(f"依赖已安装: {mod}")
        else:
            _fail(f"缺少依赖: {mod}（pip install -r assets/requirements.txt）")
            errors += 1

    # Package import
    try:
        import xjtlu_owa_mail  # noqa: F401
        from xjtlu_owa_mail import get_authenticated_client, OWAMailClient  # noqa: F401

        _ok("可导入 xjtlu_owa_mail")
    except Exception as exc:
        _fail(f"导入 xjtlu_owa_mail 失败: {exc}")
        errors += 1

    # Env
    try:
        from dotenv import load_dotenv

        repo_root = _SCRIPTS_DIR.parents[3]
        env_path = repo_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            _ok(f"找到 .env: {env_path}")
        else:
            load_dotenv()
            print("[WARN] 未找到仓库根 .env（可 cp assets/env.example .env）")
    except ImportError:
        pass

    for key in ("XJTLU_USERNAME", "XJTLU_PASSWORD", "XJTLU_OTP_URL"):
        val = os.environ.get(key)
        if val:
            _ok(f"{key} 已设置")
        else:
            print(f"[WARN] {key} 未设置（登录前需要）")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
