"""兼容入口：实现位于 skill 包内。"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent / ".cursor" / "skills" / "xjtlu-owa-mail" / "scripts"
_s = str(_SCRIPTS)
if _s not in sys.path:
    sys.path.insert(0, _s)

from xjtlu_owa_mail.owa_mail import (  # noqa: E402
    AttachmentInfo,
    FolderStats,
    MailMessage,
    MessageDetail,
    OWAMailClient,
    build_restriction,
)

__all__ = [
    "AttachmentInfo",
    "FolderStats",
    "MailMessage",
    "MessageDetail",
    "OWAMailClient",
    "build_restriction",
]
