# Python 库 API 与实现细节

CLI（`scripts/owa`）覆盖了日常需求；需要在自己的 Python 代码里组合调用时用下面的库接口。

## 快速开始

```python
import sys; sys.path.insert(0, "<SKILL_DIR>")   # 或 pip install -e <SKILL_DIR>
from xjtlu_owa_mail import get_authenticated_client, email_account

mail = get_authenticated_client(email_account())   # 三级缓存回退，失败返回 None
items = mail.find_messages("inbox", sender="Registry", since="2026-09-01", limit=10)
detail = mail.get_message(items[0].item_id, body_type="Text")
print(detail.body)
```

## 认证

`get_authenticated_client(email_account, *, force_refresh=False) -> OWAMailClient | None`

1. 读 `.cache/owa_session.json`，用 `folder_stats("inbox")` 验证会话可用
2. 失效则读 `.cache/tgc.json`，用缓存的 UIM cookie 重走微软 SSO
3. 再失效才用 `.env` 凭据完整登录 UIM（HTTP 路径，由 `xjtlu-uim-login` 包完成）

缓存目录默认为仓库下 `.cache/`（0600 权限，已 gitignore），可用 `XJTLU_OWA_CACHE_DIR` 覆盖。

底层：`login_owa(email_account, uim_cookies=None) -> (session, canary, tgc, uim_cookies)`；
`get_owa_session(tgc, email_account) -> (session, canary)`。

## OWAMailClient

构造：`OWAMailClient(session, canary)`。

| 方法 | 返回 | 说明 |
| --- | --- | --- |
| `find_messages(folder="inbox", *, sender, recipient, subject, body, since, until, unread_only, read_only, has_attachments, importance, sort_by="received", ascending=False, limit=25, offset=0)` | `list[MailMessage]` | 服务端 `Restriction` 过滤 |
| `get_message(item_id, *, body_type="Text"\|"HTML", include_attachments_meta=True)` | `MessageDetail \| None` | 正文 + 收件人 + 附件元数据 |
| `get_conversation(item_id, *, limit=50)` | `list[MailMessage]` | 同 ConversationId 的邮件 |
| `folder_stats(folder)` | `FolderStats \| None` | total / unread |
| `list_attachments(item_id)` | `list[AttachmentInfo]` | |
| `download_attachment(attachment_id, save_path)` | `Path \| None` | `save_path` 为目录时用附件原名 |
| `send_message(to, subject, body, *, cc, bcc, body_type="auto", attachments, save_to_sent=True, draft=False)` | `bool` | `attachments` 为 `(文件名, bytes\|str)` 列表 |
| `reply(item_id, body, *, reply_all=False, body_type="auto")` | `bool` | 自动查 ChangeKey |
| `forward(item_id, to, body="", *, body_type="auto")` | `bool` | |
| `mark_read(ids, *, read=True)` / `set_flag(ids, *, flagged=True)` / `categorize(ids, categories)` | `bool` | `UpdateItem` |
| `move(ids, to_folder)` | `bool` | 目标为已删除时降级为 `DeleteItem` |
| `delete(ids, *, hard=False)` | `bool` | `MoveToDeletedItems` / `HardDelete` |

数据类：`MailMessage(item_id, change_key, subject, sender, sender_email, received, is_read, has_attachments, importance, preview, size, conversation_id, raw)`、
`MessageDetail(message, body, body_type, to_recipients, cc_recipients, attachments)`、
`AttachmentInfo(attachment_id, name, content_type, size, is_inline)`、`FolderStats(folder, total, unread, child_folder_count)`。

## 正文格式（`body_type`）

OWA 对 `BodyType=HTML` 的正文按 HTML 渲染，纯文本里的 `\n` 会被折叠成空格——这是旧版"发信格式错乱"的原因。现在：

- `"auto"`（默认）：`looks_like_html()` 检测到常见标签（`<p> <br> <div> <ul> <b> <table> …`）→ 按 HTML 发；否则按 `Text` 发，Exchange 自己会转成带 `<br>` 的 HTML，换行 / 缩进 / `<` `&` 都原样保留。
- `"HTML"`：纯文本先经 `text_to_html()`（转义、空行分段成 `<p>`、单换行 `<br>`、行首空格转 `&nbsp;`）。
- `"Text"`：原样按纯文本发。

工具函数可直接导入：`from xjtlu_owa_mail.owa_mail import resolve_body, text_to_html, looks_like_html`。

## EWS JSON 方言备忘

- 端点 `POST https://mail.xjtlu.edu.cn/owa/service.svc?action=<Action>&app=Mail`，头 `Action`、`X-OWA-CANARY`、`X-Requested-With: XMLHttpRequest`。
- 请求体 `{"__type": "<Action>JsonRequest:#Exchange", "Header": {...RequestServerVersion Exchange2013, TimeZoneContext China Standard Time}, "Body": {...}}`。
- `Restriction`：`Contains`（Substring / IgnoreCase）、`IsGreaterThanOrEqualTo` / `IsLessThan`（`DateTimeReceived`，UTC `Z`）、`IsEqualTo`（`IsRead` / `HasAttachments` / `Importance`），多条件用 `And`。
- 写操作（reply / forward / UpdateItem）需要最新 `ChangeKey`，库会先 `GetItem` 拿一次。
- 此实例的 `MoveItem` 对通用文件夹不稳定，移到已删除统一走 `DeleteItem(MoveToDeletedItems)`。
- 中文界面下回复主题前缀是 `答复: `，转发是 `转发: `。

## 登录链路

1. `GET https://mail.xjtlu.edu.cn/owa/` 用 IE8 UA 拿到微软授权页的 `SAMLRequest` 表单
2. `xjtlu_uim_login.login(user, pwd, otp, idp={"action", "data"})`：HTTP 直连 UIM（UA 含 `darwin` 即被瑞数放行），`policy → doLogin → webOtpAuth`，再把 SAMLRequest 同会话 POST 到学校 IdP，返回含 `SAMLResponse` 的 HTML
3. 把 `SAMLResponse` 提交给微软，循环自动提交表单（KMSI 等）直到 cookie 里出现 `X-OWA-CANARY`

UIM 登录逻辑单独维护在 https://github.com/LYJW131/xjtlu-uim-login （含 WAF 分流结论与 jsdom 回退）。
