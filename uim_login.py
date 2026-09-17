"""兼容旧的扁平布局：`from uim_login import get_tgc_cookie` 等旧调用继续可用。新代码请直接 import xjtlu_owa_mail。"""

from xjtlu_owa_mail.uim_login import (  # noqa: F401
    REPO_DIR,
    WafChallenge,
    credentials,
    email_account,
    get_tgc,
    load_project_env,
    login,
    otp_now,
)

get_tgc_cookie = get_tgc

__all__ = [
    "REPO_DIR",
    "WafChallenge",
    "credentials",
    "email_account",
    "get_tgc",
    "get_tgc_cookie",
    "load_project_env",
    "login",
    "otp_now",
]

if __name__ == "__main__":
    print(get_tgc_cookie())
