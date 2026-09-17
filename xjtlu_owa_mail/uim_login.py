"""
UIM 登录薄封装：真正的登录逻辑在独立仓库 `xjtlu-uim-login`
（https://github.com/LYJW131/xjtlu-uim-login，纯 HTTP 走 UA 放行，412 时回退 jsdom）。

这里只做两件事：
1. 重新导出该包的接口，让本项目内部统一从 `.uim_login` 引用；
2. 补充本项目自己的辅助：REPO_DIR、email_account()。
"""

from __future__ import annotations

import os
from pathlib import Path

from xjtlu_uim_login import credentials, get_tgc, login, otp_now
from xjtlu_uim_login import load_project_env as _load_pkg_env

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent

DEFAULT_MAIL_DOMAIN = "student.xjtlu.edu.cn"

try:  # 旧版包没有 WafChallenge，这里兜底一个同名异常便于上层统一捕获
    from xjtlu_uim_login.login import WafChallenge
except ImportError:  # pragma: no cover

    class WafChallenge(RuntimeError):
        """收到 412 / 瑞数挑战页。"""


def load_project_env() -> None:
    """加载 .env：当前工作目录向上查找 → 本仓库根目录 → 登录包仓库根目录。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    _load_pkg_env()
    load_dotenv(REPO_DIR / ".env", override=False)


def email_account() -> str:
    """当前账号的完整邮箱：优先 XJTLU_EMAIL，否则 XJTLU_USERNAME@student.xjtlu.edu.cn。"""
    load_project_env()
    explicit = os.environ.get("XJTLU_EMAIL")
    if explicit:
        return explicit
    username = os.environ.get("XJTLU_USERNAME")
    if not username:
        raise ValueError("环境变量 XJTLU_USERNAME 未设置")
    if "@" in username:
        return username
    return f"{username}@{DEFAULT_MAIL_DOMAIN}"


__all__ = [
    "REPO_DIR",
    "WafChallenge",
    "credentials",
    "email_account",
    "get_tgc",
    "load_project_env",
    "login",
    "otp_now",
]
