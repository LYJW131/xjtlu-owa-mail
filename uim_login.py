"""兼容入口：UIM 登录委托给 xjtlu-uim-login 包。"""

from xjtlu_uim_login import get_tgc as get_tgc_cookie
from xjtlu_uim_login import load_project_env

__all__ = ["get_tgc_cookie", "load_project_env"]


if __name__ == "__main__":
    print(get_tgc_cookie())
