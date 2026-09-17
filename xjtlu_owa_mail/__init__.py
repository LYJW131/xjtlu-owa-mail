"""XJTLU OWA 邮件自动化：UIM 登录 → 微软 SSO → OWA service.svc（EWS JSON）。"""

from .auth import get_authenticated_client
from .owa_auth import get_owa_session, login_owa
from .owa_mail import (
    AttachmentInfo,
    FolderStats,
    MailMessage,
    MessageDetail,
    OWAMailClient,
    build_restriction,
)
from .uim_login import (
    WafChallenge,
    credentials,
    email_account,
    get_tgc,
    load_project_env,
    login,
    otp_now,
)

__all__ = [
    "AttachmentInfo",
    "FolderStats",
    "MailMessage",
    "MessageDetail",
    "OWAMailClient",
    "WafChallenge",
    "build_restriction",
    "credentials",
    "email_account",
    "get_authenticated_client",
    "get_owa_session",
    "get_tgc",
    "load_project_env",
    "login",
    "login_owa",
    "otp_now",
]
