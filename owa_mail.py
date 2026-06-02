"""
OWA 邮件操作模块
通过 OWA 内部 service.svc API（EWS JSON）实现邮件读取、搜索、发送与管理。
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Sequence, Union

SERVICE_URL = "https://mail.xjtlu.edu.cn/owa/service.svc"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
)

REQUEST_HEADER = {
    "__type": "JsonRequestHeaders:#Exchange",
    "RequestServerVersion": "Exchange2013",
    "TimeZoneContext": {
        "__type": "TimeZoneContext:#Exchange",
        "TimeZoneDefinition": {
            "__type": "TimeZoneDefinitionType:#Exchange",
            "Id": "China Standard Time",
        },
    },
}

DISTINGUISHED_FOLDERS: dict[str, str] = {
    "inbox": "inbox",
    "收件箱": "inbox",
    "sent": "sentitems",
    "sentitems": "sentitems",
    "已发送": "sentitems",
    "已发送邮件": "sentitems",
    "drafts": "drafts",
    "草稿": "drafts",
    "deleted": "deleteditems",
    "deleteditems": "deleteditems",
    "已删除": "deleteditems",
    "已删除邮件": "deleteditems",
    "junk": "junkemail",
    "junkemail": "junkemail",
    "垃圾邮件": "junkemail",
    "archive": "archive",
    "notes": "notes",
    "便笺": "notes",
}

LIST_PROPERTIES = (
    "Subject",
    "DateTimeReceived",
    "From",
    "IsRead",
    "HasAttachments",
    "Importance",
    "Preview",
    "Size",
    "ConversationId",
    "ItemId",
)

SORT_FIELDS = {
    "received": "DateTimeReceived",
    "date": "DateTimeReceived",
    "sent": "DateTimeSent",
    "subject": "Subject",
    "from": "From",
    "size": "Size",
}

ImportanceLevel = Literal["Low", "Normal", "High"]
BodyType = Literal["Text", "HTML"]
DateInput = Union[str, date, datetime]


@dataclass
class MailMessage:
    """邮件列表项摘要。"""

    item_id: str
    change_key: str = ""
    subject: str = ""
    sender: str = ""
    sender_email: str = ""
    received: str = ""
    is_read: bool = False
    has_attachments: bool = False
    importance: str = "Normal"
    preview: str = ""
    size: int = 0
    conversation_id: str = ""
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class AttachmentInfo:
    """附件元数据。"""

    attachment_id: str
    name: str
    content_type: str = ""
    size: int = 0
    is_inline: bool = False


@dataclass
class FolderStats:
    """文件夹统计。"""

    folder: str
    total: int = 0
    unread: int = 0
    child_folder_count: int = 0


@dataclass
class MessageDetail:
    """单封邮件详情（含正文）。"""

    message: MailMessage
    body: str = ""
    body_type: str = "Text"
    to_recipients: list[str] = field(default_factory=list)
    cc_recipients: list[str] = field(default_factory=list)
    attachments: list[AttachmentInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Restriction 构造（已在真实邮箱验证的 OWA JSON 方言）
# ---------------------------------------------------------------------------


def _property_uri(field_uri: str) -> dict:
    return {"__type": "PropertyUri:#Exchange", "FieldURI": field_uri}


def _constant(value: str) -> dict:
    return {"Item": {"__type": "Constant:#Exchange", "Value": value}}


def _contains(field_uri: str, text: str) -> dict:
    return {
        "__type": "Contains:#Exchange",
        "ContainmentMode": "Substring",
        "ContainmentComparison": "IgnoreCase",
        "Item": _property_uri(field_uri),
        "Constant": {"Value": text},
    }


def _compare(op: str, field_uri: str, value: str) -> dict:
    return {
        "__type": f"{op}:#Exchange",
        "Item": _property_uri(field_uri),
        "FieldURIOrConstant": _constant(value),
    }


def _and(*items: dict) -> dict:
    return {"Item": {"__type": "And:#Exchange", "Items": list(items)}}


def _or(*items: dict) -> dict:
    return {"Item": {"__type": "Or:#Exchange", "Items": list(items)}}


def _not(item: dict) -> dict:
    inner = item.get("Item", item)
    return {"Item": {"__type": "Not:#Exchange", "Item": inner}}


def build_restriction(
    *,
    sender: str | None = None,
    recipient: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    since: DateInput | None = None,
    until: DateInput | None = None,
    unread_only: bool = False,
    read_only: bool = False,
    has_attachments: bool | None = None,
    importance: ImportanceLevel | None = None,
) -> dict | None:
    """将筛选条件组合为 FindItem Restriction。"""
    parts: list[dict] = []

    if sender:
        parts.append(_contains("From", sender))
    if recipient:
        parts.append(_contains("DisplayTo", recipient))
    if subject:
        parts.append(_contains("Subject", subject))
    if body:
        parts.append(_contains("Body", body))
    if since:
        parts.append(_compare("IsGreaterThanOrEqualTo", "DateTimeReceived", _to_ews_datetime(since)))
    if until:
        parts.append(_compare("IsLessThan", "DateTimeReceived", _to_ews_datetime(until)))
    if unread_only:
        parts.append(_compare("IsEqualTo", "IsRead", "false"))
    if read_only:
        parts.append(_compare("IsEqualTo", "IsRead", "true"))
    if has_attachments is True:
        parts.append(_compare("IsEqualTo", "HasAttachments", "true"))
    elif has_attachments is False:
        parts.append(_compare("IsEqualTo", "HasAttachments", "false"))
    if importance:
        parts.append(_compare("IsEqualTo", "Importance", importance))

    if not parts:
        return None
    if len(parts) == 1:
        return {"Item": parts[0]}
    return _and(*parts)


def _to_ews_datetime(value: DateInput) -> str:
    if isinstance(value, datetime):
        dt = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return f"{value.isoformat()}T00:00:00Z"
    text = str(value).strip()
    if "T" not in text:
        return f"{text}T00:00:00Z"
    if not text.endswith("Z") and "+" not in text[-6:]:
        return f"{text}Z" if text.endswith("Z") is False else text
    return text


def _item_shape(
    extra_fields: Sequence[str] | None = None,
    base_shape: str = "IdOnly",
) -> dict:
    fields = list(LIST_PROPERTIES)
    if extra_fields:
        for f in extra_fields:
            if f not in fields:
                fields.append(f)
    return {
        "__type": "ItemResponseShape:#Exchange",
        "BaseShape": base_shape,
        "AdditionalProperties": [_property_uri(f) for f in fields if f != "ItemId"],
    }


def _email_address(addr: str, name: str = "") -> dict:
    return {
        "__type": "EmailAddress:#Exchange",
        "RoutingType": "SMTP",
        "EmailAddress": addr,
        "Name": name or addr,
    }


def _parse_mailbox_list(recipients: Any) -> list[str]:
    if not recipients:
        return []
    items = recipients if isinstance(recipients, list) else [recipients]
    out: list[str] = []
    for r in items:
        if isinstance(r, dict):
            mb = r.get("Mailbox") or r
            email = mb.get("EmailAddress", "")
            if email:
                out.append(email)
    return out


def _item_to_message(item: dict) -> MailMessage:
    mailbox = (item.get("From") or {}).get("Mailbox") or {}
    item_id = item.get("ItemId") or {}
    conv = item.get("ConversationId") or {}
    preview = (item.get("Preview") or "").replace("\r", " ").replace("\n", " ")
    return MailMessage(
        item_id=item_id.get("Id", ""),
        change_key=item_id.get("ChangeKey", ""),
        subject=(item.get("Subject") or "").strip() or "(无主题)",
        sender=mailbox.get("Name", ""),
        sender_email=mailbox.get("EmailAddress", ""),
        received=item.get("DateTimeReceived", ""),
        is_read=bool(item.get("IsRead")),
        has_attachments=bool(item.get("HasAttachments")),
        importance=item.get("Importance", "Normal"),
        preview=preview,
        size=int(item.get("Size") or 0),
        conversation_id=conv.get("Id", "") if isinstance(conv, dict) else str(conv or ""),
        raw=item,
    )


# ---------------------------------------------------------------------------
# OWA 客户端
# ---------------------------------------------------------------------------


class OWAMailClient:
    """OWA 邮件库式客户端。"""

    def __init__(self, session, canary: str):
        if not session or not canary:
            raise ValueError("需要有效的 session 与 X-OWA-CANARY")
        self.session = session
        self.canary = canary
        self._folder_cache: dict[str, dict] = {}

    def _build_headers(self, action: str) -> dict:
        return {
            "X-Requested-With": "XMLHttpRequest",
            "Action": action,
            "Content-Type": "application/json; charset=utf-8",
            "X-OWA-CANARY": self.canary,
            "User-Agent": USER_AGENT,
        }

    def _post(self, action: str, body: dict, request_type: str) -> dict | None:
        url = f"{SERVICE_URL}?action={action}&app=Mail"
        payload = {
            "__type": f"{request_type}:#Exchange",
            "Header": REQUEST_HEADER,
            "Body": body,
        }
        res = self.session.post(url, headers=self._build_headers(action), json=payload)
        if res.status_code != 200:
            return None
        return res.json()

    def _first_response(self, data: dict | None) -> dict | None:
        if not data:
            return None
        try:
            return data["Body"]["ResponseMessages"]["Items"][0]
        except (KeyError, IndexError, TypeError):
            return None

    def _response_ok(self, data: dict | None) -> bool:
        msg = self._first_response(data)
        return bool(msg and msg.get("ResponseCode") == "NoError")

    def _resolve_folder_id(self, folder: str) -> dict:
        key = folder.strip().lower()
        if key in DISTINGUISHED_FOLDERS:
            return {
                "__type": "DistinguishedFolderId:#Exchange",
                "Id": DISTINGUISHED_FOLDERS[key],
            }
        cached = self._folder_cache.get(folder)
        if cached:
            return cached
        found = self._find_folder_by_name(folder)
        if found:
            self._folder_cache[folder] = found
            return found
        raise ValueError(f"未知文件夹: {folder}")

    def _find_folder_by_name(self, name: str) -> dict | None:
        body = {
            "__type": "FindFolderRequest:#Exchange",
            "Traversal": "Deep",
            "FolderShape": {
                "__type": "FolderResponseShape:#Exchange",
                "BaseShape": "Default",
                "AdditionalProperties": [_property_uri("DisplayName")],
            },
            "ParentFolderIds": [
                {
                    "__type": "DistinguishedFolderId:#Exchange",
                    "Id": "msgfolderroot",
                }
            ],
        }
        resp = self._post("FindFolder", body, "FindFolderJsonRequest")
        msg = self._first_response(resp)
        if not msg:
            return None
        folders = msg.get("RootFolder", {}).get("Folders") or []

        def walk(nodes: list) -> dict | None:
            for node in nodes:
                display = (node.get("DisplayName") or "").strip()
                if display.lower() == name.strip().lower():
                    fid = node.get("FolderId") or {}
                    return {
                        "__type": "FolderId:#Exchange",
                        "Id": fid.get("Id", ""),
                        "ChangeKey": fid.get("ChangeKey", ""),
                    }
                sub = node.get("ChildFolders") or node.get("Folders")
                if sub:
                    hit = walk(sub if isinstance(sub, list) else [sub])
                    if hit:
                        return hit
            return None

        return walk(folders if isinstance(folders, list) else [folders])

    # --- 搜索 / 列表 ---

    def find_messages(
        self,
        folder: str = "inbox",
        *,
        sender: str | None = None,
        recipient: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        since: DateInput | None = None,
        until: DateInput | None = None,
        unread_only: bool = False,
        read_only: bool = False,
        has_attachments: bool | None = None,
        importance: ImportanceLevel | None = None,
        sort_by: str = "received",
        ascending: bool = False,
        limit: int = 25,
        offset: int = 0,
    ) -> list[MailMessage]:
        """按条件搜索文件夹中的邮件。"""
        restriction = build_restriction(
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            since=since,
            until=until,
            unread_only=unread_only,
            read_only=read_only,
            has_attachments=has_attachments,
            importance=importance,
        )
        sort_field = SORT_FIELDS.get(sort_by.lower(), "DateTimeReceived")
        req: dict[str, Any] = {
            "__type": "FindItemRequest:#Exchange",
            "ItemShape": _item_shape(),
            "ParentFolderIds": [self._resolve_folder_id(folder)],
            "Traversal": "Shallow",
            "Paging": {
                "__type": "IndexedPageView:#Exchange",
                "BasePoint": "Beginning",
                "Offset": offset,
                "MaxEntriesReturned": limit,
            },
            "ViewFilter": "All",
            "ClutterFilter": "All",
            "SortOrder": [
                {
                    "__type": "SortResults:#Exchange",
                    "Order": "Ascending" if ascending else "Descending",
                    "Path": _property_uri(sort_field),
                }
            ],
        }
        if restriction:
            req["Restriction"] = restriction

        resp = self._post("FindItem", req, "FindItemJsonRequest")
        msg = self._first_response(resp)
        if not msg or msg.get("ResponseCode") != "NoError":
            return []
        items = (msg.get("RootFolder") or {}).get("Items") or []
        return [_item_to_message(it) for it in items]

    # --- 正文 / 会话 / 统计 ---

    def get_message(
        self,
        item_id: str,
        *,
        body_type: BodyType = "Text",
        include_attachments_meta: bool = True,
    ) -> MessageDetail | None:
        """获取单封邮件完整正文与元数据。"""
        shape: dict[str, Any] = {
            "__type": "ItemResponseShape:#Exchange",
            "BaseShape": "AllProperties",
            "BodyType": body_type,
            "FilterHtmlContent": False,
            "AddBlankTargetToLinks": False,
            "MaximumBodySize": 2097152,
        }
        if include_attachments_meta:
            shape["AdditionalProperties"] = [_property_uri("Attachments")]

        body = {
            "__type": "GetItemRequest:#Exchange",
            "ItemShape": shape,
            "ItemIds": [{"__type": "ItemId:#Exchange", "Id": item_id}],
        }
        resp = self._post("GetItem", body, "GetItemJsonRequest")
        msg = self._first_response(resp)
        if not msg or msg.get("ResponseCode") != "NoError":
            return None
        items = msg.get("Items") or []
        if not items:
            return None
        item = items[0]
        body_field = item.get("NormalizedBody") or item.get("Body") or {}
        attachments: list[AttachmentInfo] = []
        for att in item.get("Attachments") or []:
            att_id = att.get("AttachmentId") or att.get("ItemId") or {}
            attachments.append(
                AttachmentInfo(
                    attachment_id=att_id.get("Id", "") if isinstance(att_id, dict) else str(att_id),
                    name=att.get("Name", "attachment"),
                    content_type=att.get("ContentType", ""),
                    size=int(att.get("Size") or 0),
                    is_inline=bool(att.get("IsInline")),
                )
            )
        mail = _item_to_message(item)
        return MessageDetail(
            message=mail,
            body=body_field.get("Value", ""),
            body_type=body_type,
            to_recipients=_parse_mailbox_list(item.get("ToRecipients")),
            cc_recipients=_parse_mailbox_list(item.get("CcRecipients")),
            attachments=attachments,
        )

    def get_conversation(self, item_id: str, *, limit: int = 50) -> list[MailMessage]:
        """获取同一会话线程中的邮件列表。"""
        detail = self.get_message(item_id, body_type="Text", include_attachments_meta=False)
        if not detail or not detail.message.conversation_id:
            return [detail.message] if detail else []

        conv_id = detail.message.conversation_id
        body = {
            "__type": "FindItemRequest:#Exchange",
            "ItemShape": _item_shape(),
            "ParentFolderIds": [self._resolve_folder_id("inbox")],
            "Traversal": "Shallow",
            "Paging": {
                "__type": "IndexedPageView:#Exchange",
                "BasePoint": "Beginning",
                "Offset": 0,
                "MaxEntriesReturned": limit,
            },
            "Restriction": _compare("IsEqualTo", "ConversationId", conv_id),
        }
        # ConversationId 比较可能需 IndexedField；回退：拉最近邮件再过滤
        resp = self._post("FindItem", body, "FindItemJsonRequest")
        msg = self._first_response(resp)
        if msg and msg.get("ResponseCode") == "NoError":
            items = (msg.get("RootFolder") or {}).get("Items") or []
            matched = [m for m in (_item_to_message(it) for it in items) if m.conversation_id == conv_id]
            if matched:
                return matched

        # 回退：扫描收件箱最近邮件
        recent = self.find_messages("inbox", limit=min(limit * 4, 200))
        return [m for m in recent if m.conversation_id == conv_id]

    def folder_stats(self, folder: str = "inbox") -> FolderStats | None:
        """获取文件夹总数与未读数。"""
        body = {
            "__type": "GetFolderRequest:#Exchange",
            "FolderShape": {
                "__type": "FolderResponseShape:#Exchange",
                "BaseShape": "Default",
                "AdditionalProperties": [
                    _property_uri("TotalCount"),
                    _property_uri("UnreadCount"),
                    _property_uri("ChildFolderCount"),
                ],
            },
            "FolderIds": [self._resolve_folder_id(folder)],
        }
        resp = self._post("GetFolder", body, "GetFolderJsonRequest")
        msg = self._first_response(resp)
        if not msg or msg.get("ResponseCode") != "NoError":
            return None
        folders = msg.get("Folders") or []
        if not folders:
            return None
        f = folders[0]
        return FolderStats(
            folder=folder,
            total=int(f.get("TotalCount") or 0),
            unread=int(f.get("UnreadCount") or 0),
            child_folder_count=int(f.get("ChildFolderCount") or 0),
        )

    # --- 附件 ---

    def list_attachments(self, item_id: str) -> list[AttachmentInfo]:
        detail = self.get_message(item_id, body_type="Text", include_attachments_meta=True)
        return detail.attachments if detail else []

    def download_attachment(
        self,
        attachment_id: str,
        save_path: str | Path,
        *,
        item_id: str | None = None,
    ) -> Path | None:
        """
        下载附件到本地。

        :param attachment_id: AttachmentId；若仅有 item_id 可先 list_attachments
        :param save_path: 文件路径或目录（目录时使用附件原名）
        """
        att_ids = [{"__type": "AttachmentId:#Exchange", "Id": attachment_id}]
        body = {
            "__type": "GetAttachmentRequest:#Exchange",
            "AttachmentIds": att_ids,
        }
        resp = self._post("GetAttachment", body, "GetAttachmentJsonRequest")
        msg = self._first_response(resp)
        if not msg or msg.get("ResponseCode") != "NoError":
            return None
        attachments = msg.get("Attachments") or []
        if not attachments:
            return None
        att = attachments[0]
        content_b64 = att.get("Content") or ""
        if not content_b64:
            return None
        data = base64.b64decode(content_b64)
        save_path = Path(save_path)
        if save_path.is_dir():
            save_path = save_path / (att.get("Name") or "attachment")
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(data)
        return save_path

    # --- 发信 ---

    def _build_message_item(
        self,
        to: str | Sequence[str],
        subject: str,
        body: str,
        *,
        cc: str | Sequence[str] | None = None,
        bcc: str | Sequence[str] | None = None,
        body_type: BodyType = "HTML",
        attachments: Sequence[tuple[str, bytes | str]] | None = None,
    ) -> dict:
        def as_list(v: str | Sequence[str] | None) -> list[str]:
            if v is None:
                return []
            if isinstance(v, str):
                return [v]
            return list(v)

        item: dict[str, Any] = {
            "__type": "Message:#Exchange",
            "Subject": subject,
            "Body": {
                "__type": "BodyContentType:#Exchange",
                "BodyType": body_type,
                "Value": body,
            },
            "ToRecipients": [_email_address(a) for a in as_list(to)],
        }
        cc_list = as_list(cc)
        bcc_list = as_list(bcc)
        if cc_list:
            item["CcRecipients"] = [_email_address(a) for a in cc_list]
        if bcc_list:
            item["BccRecipients"] = [_email_address(a) for a in bcc_list]
        if attachments:
            att_items = []
            for name, content in attachments:
                if isinstance(content, str):
                    raw = content.encode("utf-8")
                else:
                    raw = content
                att_items.append(
                    {
                        "__type": "FileAttachment:#Exchange",
                        "Name": name,
                        "Content": base64.b64encode(raw).decode("ascii"),
                        "ContentType": "application/octet-stream",
                    }
                )
            item["Attachments"] = att_items
        return item

    def send_message(
        self,
        to: str | Sequence[str],
        subject: str,
        body: str,
        *,
        cc: str | Sequence[str] | None = None,
        bcc: str | Sequence[str] | None = None,
        body_type: BodyType = "HTML",
        attachments: Sequence[tuple[str, bytes | str]] | None = None,
        save_to_sent: bool = True,
        draft: bool = False,
    ) -> bool:
        """发送邮件或保存草稿。"""
        item = self._build_message_item(
            to, subject, body, cc=cc, bcc=bcc, body_type=body_type, attachments=attachments
        )
        disposition = "SaveOnly" if draft else ("SendAndSaveCopy" if save_to_sent else "SendOnly")
        req = {
            "__type": "CreateItemRequest:#Exchange",
            "Items": [item],
            "MessageDisposition": disposition,
        }
        resp = self._post("CreateItem", req, "CreateItemJsonRequest")
        return self._response_ok(resp)

    # --- 回复 / 转发 ---

    def _get_change_key(self, item_id: str) -> str:
        """获取 item 的最新 ChangeKey（写操作必须提供）。"""
        detail = self.get_message(item_id, body_type="Text", include_attachments_meta=False)
        return detail.message.change_key if detail else ""

    def reply(
        self,
        item_id: str,
        body: str,
        *,
        reply_all: bool = False,
        body_type: BodyType = "HTML",
        change_key: str = "",
    ) -> bool:
        """回复邮件。OWA 写操作要求 ChangeKey；未传时自动查询。"""
        ck = change_key or self._get_change_key(item_id)
        item_type = "ReplyAllToItem:#Exchange" if reply_all else "ReplyToItem:#Exchange"
        ref_id: dict[str, Any] = {"__type": "ItemId:#Exchange", "Id": item_id}
        if ck:
            ref_id["ChangeKey"] = ck
        req = {
            "__type": "CreateItemRequest:#Exchange",
            "Items": [
                {
                    "__type": item_type,
                    "ReferenceItemId": ref_id,
                    "NewBodyContent": {
                        "__type": "BodyContentType:#Exchange",
                        "BodyType": body_type,
                        "Value": body,
                    },
                }
            ],
            "MessageDisposition": "SendAndSaveCopy",
        }
        resp = self._post("CreateItem", req, "CreateItemJsonRequest")
        return self._response_ok(resp)

    def forward(
        self,
        item_id: str,
        to: str | Sequence[str],
        body: str = "",
        *,
        body_type: BodyType = "HTML",
        change_key: str = "",
    ) -> bool:
        """转发邮件。OWA 写操作要求 ChangeKey；未传时自动查询。"""
        ck = change_key or self._get_change_key(item_id)
        to_list = [to] if isinstance(to, str) else list(to)
        ref_id: dict[str, Any] = {"__type": "ItemId:#Exchange", "Id": item_id}
        if ck:
            ref_id["ChangeKey"] = ck
        req = {
            "__type": "CreateItemRequest:#Exchange",
            "Items": [
                {
                    "__type": "ForwardItem:#Exchange",
                    "ReferenceItemId": ref_id,
                    "ToRecipients": [_email_address(a) for a in to_list],
                    "NewBodyContent": {
                        "__type": "BodyContentType:#Exchange",
                        "BodyType": body_type,
                        "Value": body,
                    },
                }
            ],
            "MessageDisposition": "SendAndSaveCopy",
        }
        resp = self._post("CreateItem", req, "CreateItemJsonRequest")
        return self._response_ok(resp)

    # --- 管理写操作 ---

    def _update_items(self, item_ids: Sequence[str], updates: list[dict]) -> bool:
        changes = []
        for iid in item_ids:
            changes.append(
                {
                    "__type": "ItemChange:#Exchange",
                    "ItemId": {"__type": "ItemId:#Exchange", "Id": iid},
                    "Updates": updates,
                }
            )
        req = {
            "__type": "UpdateItemRequest:#Exchange",
            "ConflictResolution": "AlwaysOverwrite",
            "MessageDisposition": "SaveOnly",
            "ItemChanges": changes,
        }
        resp = self._post("UpdateItem", req, "UpdateItemJsonRequest")
        return self._response_ok(resp)

    def mark_read(self, item_ids: str | Sequence[str], *, read: bool = True) -> bool:
        ids = [item_ids] if isinstance(item_ids, str) else list(item_ids)
        updates = [
            {
                "__type": "SetItemField:#Exchange",
                "Path": _property_uri("IsRead"),
                "Item": {"__type": "Message:#Exchange", "IsRead": read},
            }
        ]
        return self._update_items(ids, updates)

    def move(self, item_ids: str | Sequence[str], to_folder: str) -> bool:
        """移动邮件到指定文件夹。
        注意：此 OWA 实例的 service.svc JSON API 不支持通用 MoveItem 操作。
        移动到已删除文件夹（deleted/deleteditems）时自动降级为 DeleteItem(MoveToDeletedItems)。
        """
        ids = [item_ids] if isinstance(item_ids, str) else list(item_ids)
        dest = DISTINGUISHED_FOLDERS.get(to_folder.strip().lower(), to_folder.strip().lower())
        if dest == "deleteditems":
            return self.delete(ids, hard=False)
        req = {
            "__type": "MoveItemRequest:#Exchange",
            "ToFolderId": self._resolve_folder_id(to_folder),
            "ItemIds": [{"__type": "ItemId:#Exchange", "Id": i} for i in ids],
        }
        resp = self._post("MoveItem", req, "MoveItemJsonRequest")
        return self._response_ok(resp)

    def delete(self, item_ids: str | Sequence[str], *, hard: bool = False) -> bool:
        ids = [item_ids] if isinstance(item_ids, str) else list(item_ids)
        delete_type = "HardDelete" if hard else "MoveToDeletedItems"
        req = {
            "__type": "DeleteItemRequest:#Exchange",
            "DeleteType": delete_type,
            "ItemIds": [{"__type": "ItemId:#Exchange", "Id": i} for i in ids],
        }
        resp = self._post("DeleteItem", req, "DeleteItemJsonRequest")
        return self._response_ok(resp)

    def set_flag(self, item_ids: str | Sequence[str], *, flagged: bool = True) -> bool:
        ids = [item_ids] if isinstance(item_ids, str) else list(item_ids)
        flag_status = "Flagged" if flagged else "NotFlagged"
        updates = [
            {
                "__type": "SetItemField:#Exchange",
                "Path": _property_uri("Flag"),
                "Item": {"__type": "Message:#Exchange", "Flag": {"__type": "FlagType:#Exchange", "FlagStatus": flag_status}},
            }
        ]
        return self._update_items(ids, updates)

    def categorize(self, item_ids: str | Sequence[str], categories: Sequence[str]) -> bool:
        ids = [item_ids] if isinstance(item_ids, str) else list(item_ids)
        updates = [
            {
                "__type": "SetItemField:#Exchange",
                "Path": _property_uri("Categories"),
                "Item": {
                    "__type": "Message:#Exchange",
                    "Categories": list(categories),
                },
            }
        ]
        return self._update_items(ids, updates)


