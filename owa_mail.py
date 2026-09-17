"""兼容旧的扁平布局：`from owa_mail import ...` 现在转发到 xjtlu_owa_mail.owa_mail。新代码请直接 import xjtlu_owa_mail。"""

from xjtlu_owa_mail.owa_mail import *  # noqa: F401,F403
from xjtlu_owa_mail.owa_mail import __dict__ as _pkg_dict  # noqa: F401

globals().update({k: v for k, v in _pkg_dict.items() if not k.startswith("__")})
