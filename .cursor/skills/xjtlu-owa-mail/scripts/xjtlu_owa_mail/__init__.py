"""XJTLU OWA Mail — UIM 登录 + OWA 邮件客户端。"""

from .auth import get_authenticated_client
from .owa_mail import (
    AttachmentInfo,
    FolderStats,
    MailMessage,
    MessageDetail,
    OWAMailClient,
)

__all__ = [
    "get_authenticated_client",
    "OWAMailClient",
    "MailMessage",
    "MessageDetail",
    "AttachmentInfo",
    "FolderStats",
]
