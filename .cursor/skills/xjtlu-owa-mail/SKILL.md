---
name: xjtlu-owa-mail
description: >-
  通过 XJTLU UIM 自动登录 OWA 邮箱，以 Python 库读写/搜索/发送/管理邮件。
  在用户需要操作 XJTLU 学生邮箱、OWA、mail.xjtlu.edu.cn、UIM 登录或邮件自动化时使用。
---

# XJTLU OWA Mail

用学校 UIM（统一身份认证）完成 OWA SSO，拿到可用会话后，通过 `OWAMailClient` 操作邮箱。无需手动复制 Cookie，也不启动完整浏览器。

## When to use

- 读取 / 搜索 / 统计 XJTLU OWA 邮件
- 下载附件、发信、回复、转发
- 标记已读、移动、删除、打旗标、分类（会改邮箱，需确认）
- 排查 UIM → 微软 SSO → OWA 登录或会话缓存问题

## Prerequisites

1. Python 3.12+
2. 安装依赖：`pip install -r assets/requirements.txt`（或仓库根 `requirements.txt`）
3. 配置凭证：复制 `assets/env.example` 为仓库根 `.env`，填写：
   - `XJTLU_USERNAME`（不含 `@student.xjtlu.edu.cn`）
   - `XJTLU_PASSWORD`
   - `XJTLU_OTP_URL`（`otpauth://` 开头的 TOTP）
4. 可选：Node.js 18+（仅当 UIM HTTP 路径返回 412 时，`xjtlu-uim-login` 会回退 jsdom）

先跑自检（不发起登录）：

```bash
python scripts/check_setup.py
```

## Agent workflow

1. **读本 skill**，需要细节时再打开 `references/`（渐进加载）。
2. **确认 `.env` 存在且未提交**；不要把真实密码/OTP 写进代码或提交到 git。
3. **默认只做只读操作**（`folder_stats` / `find_messages` / `get_message`）。发信、删除、移动等写操作必须先征得用户明确同意。
4. **入口优先用缓存认证**：

```python
import sys
from pathlib import Path

# 本 skill 的 scripts/ 加入 path（按实际 skill 根目录调整）
scripts = Path("...") / "scripts"  # 即本文件同级的 scripts/
sys.path.insert(0, str(scripts))

from xjtlu_owa_mail import get_authenticated_client

email = f"{username}@student.xjtlu.edu.cn"
mail = get_authenticated_client(email)
```

在本仓库根目录也可：`from auth import get_authenticated_client`（兼容 shim）。

5. **演示脚本**（写操作默认注释）：

```bash
python scripts/example.py
```

## Auth cache (三级回退)

`get_authenticated_client(email)`：

1. `.cache/owa_session.json` → 验证可用则直接返回
2. 否则用 `.cache/tgc.json` 重登 OWA
3. 再否则完整 UIM 登录 → 写回缓存

缓存权限 `0600`，已被 `.gitignore` 忽略。`force_refresh=True` 可跳过缓存。

详情见 [references/auth-flow.md](references/auth-flow.md)。

## API cheat sheet

| 能力 | 方法 |
| --- | --- |
| 搜索 | `find_messages(folder, sender=, subject=, since=, unread_only=, limit=, ...)` |
| 正文 | `get_message(item_id, body_type="Text"\|"HTML")` |
| 会话 | `get_conversation(item_id)` |
| 统计 | `folder_stats(folder)` |
| 附件 | `list_attachments` / `download_attachment` |
| 发信 | `send_message(to, subject, body, cc=, bcc=, attachments=, draft=)` |
| 回复/转发 | `reply` / `forward` |
| 管理 | `mark_read` / `move` / `delete` / `set_flag` / `categorize` |

文件夹别名：`inbox` / `sent` / `drafts` / `deleted` / `junk` / `archive` 等。

完整签名与数据结构见 [references/api.md](references/api.md)。约束与故障见 [references/constraints.md](references/constraints.md)。

## Constraints

- 仅用于个人邮箱自动化学习；遵守学校规定。
- 不要提交 `.env`、`.cache/`、真实 Cookie / TGC。
- 写操作默认不执行；示例里保持注释，除非用户要求。
- `ProxyError` / `SSLError` 多为本地网络无法访问微软登录域，不是业务逻辑 bug。
- UIM 瑞数细节委托外部包 [`xjtlu-uim-login`](https://github.com/LYJW131/xjtlu-uim-login)；本 skill 不重复维护瑞数绕过逻辑。

## Layout

```text
xjtlu-owa-mail/
├── SKILL.md                 # 本文件
├── scripts/
│   ├── xjtlu_owa_mail/      # Python 包（权威源码）
│   ├── example.py
│   └── check_setup.py
├── references/
│   ├── api.md
│   ├── auth-flow.md
│   └── constraints.md
└── assets/
    ├── env.example
    └── requirements.txt
```
