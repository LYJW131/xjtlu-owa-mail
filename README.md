# XJTLU OWA Mail

通过 XJTLU 统一身份认证（UIM）自动登录，获取 OWA 邮箱会话，以 **Python 库** 方式读取、搜索、发送与管理邮件。

整个流程无需手动复制 Cookie，也不启动完整浏览器。UIM 登录复用独立包 [`xjtlu-uim-login`](https://github.com/LYJW131/xjtlu-uim-login)（jsdom 过瑞数 412 + `doLogin`）。微软 SSO 用 IE 兼容页拿 `SAMLRequest`，再在同一次 jsdom 会话里交给学校 IdP。

## 功能

| 模块 | 能力 |
| --- | --- |
| `xjtlu-uim-login` | 外部包：UIM 瑞数挑战 + `doLogin` + 可选 IdP |
| `uim_login.py` | 兼容入口，转调 `xjtlu_uim_login.get_tgc` |
| `owa_auth.py` | 微软 SAML + KMSI，返回 `session` + `X-OWA-CANARY` |
| `owa_mail.py` | **`OWAMailClient`**：搜索、正文、会话、附件、发信、回复/转发、标记/移动/删除 |
| `auth.py` | 双层认证缓存（OWA 会话缓存 → TGC 缓存 → UIM 登录） |

### `OWAMailClient` API 摘要

**搜索 / 读取**

- `find_messages(folder, sender=, recipient=, subject=, body=, since=, until=, unread_only=, has_attachments=, importance=, sort_by=, limit=, offset=)`  
  服务端 `Restriction` 过滤（发件人/主题/正文/日期/未读/附件等），支持 `inbox` / `sent` / `drafts` / `deleted` / `junk` / `archive` 等文件夹别名。

**正文 / 统计**

- `get_message(item_id, body_type="Text"\|"HTML")` → `MessageDetail`（正文 + 收件人 + 附件元数据）
- `get_conversation(item_id)` → 同会话线程邮件列表
- `folder_stats(folder)` → 总数 / 未读数

**附件**

- `list_attachments(item_id)`
- `download_attachment(attachment_id, save_path)`

**发信**

- `send_message(to, subject, body, cc=, bcc=, body_type=, attachments=, draft=)`  
  `attachments` 为 `(文件名, bytes|str)` 列表。

**回复 / 转发**

- `reply(item_id, body, reply_all=False)`
- `forward(item_id, to, body)`

**管理（会修改邮箱）**

- `mark_read(item_ids, read=True)`
- `move(item_ids, to_folder)`
- `delete(item_ids, hard=False)`
- `set_flag(item_ids, flagged=True)`
- `categorize(item_ids, categories)`

## 认证缓存机制

`auth.get_authenticated_client(email_account)` 默认使用三级回退：

1. 先读取 `.cache/owa_session.json` 并验证缓存会话是否可用  
2. OWA 会话失效时，读取 `.cache/tgc.json` 用缓存 TGC 重登 OWA  
3. TGC 失效时，调用 UIM 完整登录获取新 TGC，再登录 OWA

缓存文件仅保存在本地并设置为 `0600` 权限，且已被 `.gitignore` 忽略。

## 环境要求

- Python 3.12+
- Node.js 18+（`xjtlu-uim-login` 首次运行会自动 `npm install jsdom`）
- 依赖见 `requirements.txt`

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置

```bash
cp .env.example .env
```

| 变量 | 说明 |
| --- | --- |
| `XJTLU_USERNAME` | UIM 用户名（不含 `@student.xjtlu.edu.cn`） |
| `XJTLU_PASSWORD` | UIM 登录密码 |
| `XJTLU_OTP_URL` | OTP 地址，`otpauth://` 开头 |

> `.env` 已被 `.gitignore` 忽略。请勿将真实凭证提交到仓库。

## 使用示例

```python
from auth import get_authenticated_client

email = "Yourname.Lastname25@student.xjtlu.edu.cn"
mail = get_authenticated_client(email)
if not mail:
    raise SystemExit("认证失败")

# 搜索：某发件人、5月29日之后、未读
items = mail.find_messages(
    "inbox",
    sender="Registry",
    since="2026-05-29",
    unread_only=True,
    limit=20,
)

# 读正文
if items:
    detail = mail.get_message(items[0].item_id, body_type="HTML")
    print(detail.body)

# 文件夹统计
print(mail.folder_stats("inbox"))
```

运行演示：

```bash
python3 example.py
```

`example.py` 中标记已读、发信、删除等写操作默认注释，按需取消。

## 代码结构

| 文件 | 职责 |
| --- | --- |
| `example.py` | 使用 `auth.get_authenticated_client` 的完整调用示例 |
| `uim_login.py` | 兼容入口（`xjtlu_uim_login.get_tgc`） |
| `owa_auth.py` | 微软 SAMLRequest + KMSI → OWA |
| `owa_mail.py` | 邮件库（`OWAMailClient`、`MailMessage` 等） |
| `auth.py` | 本地认证缓存与会话回退 |

## 说明

- 本项目仅用于个人邮箱自动化学习用途，请遵守学校相关规定。
- 瑞数会给 XHR 自动加上 `KgdICDMu`；页面上的 `/sso-mfa/rest/ueba/send` 只服务浏览器 UI，JSON `doLogin` 不依赖它。
- 筛选条件通过 EWS `Restriction` 在服务端执行（已在 XJTLU OWA 实测验证 JSON 方言）。
- 若出现 `ProxyError` / `SSLError`，多为本地网络无法访问微软登录域名，与代码逻辑无关。
