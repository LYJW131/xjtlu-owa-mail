# OWAMailClient API

权威实现：`scripts/xjtlu_owa_mail/owa_mail.py`。入口：`get_authenticated_client`（`scripts/xjtlu_owa_mail/auth.py`）。

## 获取客户端

```python
from xjtlu_owa_mail import get_authenticated_client

mail = get_authenticated_client(
    "Yourname.Lastname25@student.xjtlu.edu.cn",
    force_refresh=False,  # True 跳过缓存，强制 UIM 全量登录
)
```

返回 `OWAMailClient | None`。

## 数据类型

- `MailMessage`：列表项（`item_id`, `subject`, `sender`, `sender_email`, `received`, `is_read`, `has_attachments`, `preview`, …）
- `MessageDetail`：正文详情（`body`, 收件人, `attachments`）
- `AttachmentInfo`：附件元数据（`attachment_id`, `name`, `size`, …）
- `FolderStats`：`total` / `unread`

## 搜索 / 读取

```python
items = mail.find_messages(
    "inbox",
    sender="Registry",
    recipient=None,
    subject=None,
    body=None,
    since="2026-05-29",   # str | date | datetime
    until=None,
    unread_only=True,
    read_only=False,
    has_attachments=None,
    importance=None,      # "Low" | "Normal" | "High"
    sort_by="received",
    ascending=False,
    limit=20,
    offset=0,
)

detail = mail.get_message(items[0].item_id, body_type="HTML")  # 或 "Text"
thread = mail.get_conversation(items[0].item_id, limit=10)
stats = mail.folder_stats("inbox")
```

筛选条件经 EWS `Restriction` 在服务端执行。文件夹别名：`inbox` / `sent` / `drafts` / `deleted` / `junk` / `archive`；也支持按显示名查找。

## 附件

```python
atts = mail.list_attachments(item_id)
path = mail.download_attachment(attachment_id, save_path="./downloads")
```

## 发信

```python
mail.send_message(
    to=["a@student.xjtlu.edu.cn"],
    subject="标题",
    body="<p>正文</p>",
    cc=["c@example.com"],
    bcc=["b@example.com"],
    body_type="HTML",
    attachments=[("file.pdf", pdf_bytes)],  # (文件名, bytes|str)
    draft=False,
)
```

## 回复 / 转发

```python
mail.reply(item_id, "<p>收到</p>", reply_all=False)
mail.forward(item_id, ["other@student.xjtlu.edu.cn"], "请查收")
```

## 管理（会修改邮箱）

```python
mail.mark_read(item_ids, read=True)
mail.move(item_ids, to_folder="deleted")
mail.delete(item_ids, hard=False)
mail.set_flag(item_ids, flagged=True)
mail.categorize(item_ids, categories=["Blue category"])
```

`item_ids` 可为单个 id 或列表。
