# XJTLU OWA Mail

通过 XJTLU 统一身份认证（UIM）自动登录，获取 OWA 邮箱会话，以 **Python 库** 与 **Cursor Skill** 方式读取、搜索、发送与管理邮件。

整个流程无需手动复制 Cookie，也不启动完整浏览器。UIM 登录复用独立包 [`xjtlu-uim-login`](https://github.com/LYJW131/xjtlu-uim-login)。

## 两种用法

### 1. Cursor Skill（推荐给 Agent）

本仓库在 `.cursor/skills/xjtlu-owa-mail/` 提供规范 skill（`SKILL.md` + `scripts/` + `references/` + `assets/`）。

| 安装方式 | 做法 |
| --- | --- |
| 打开本仓库作项目 | Cursor 自动发现 `.cursor/skills/` |
| 用户级 skill | 将 `.cursor/skills/xjtlu-owa-mail` 复制/软链到 `~/.cursor/skills/xjtlu-owa-mail` |
| 插件 | 仓库根有 `.cursor-plugin/plugin.json`，可用 Customize → From GitHub Repository 导入（需按 Cursor 插件流程） |

Agent 侧入口说明见 skill 内 `SKILL.md`；详细 API / 认证 / 约束在 `references/`。

### 2. Python 库（本仓库根目录保持可运行）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填写凭证
python3 .cursor/skills/xjtlu-owa-mail/scripts/check_setup.py
python3 example.py
```

根目录 `auth.py` / `owa_mail.py` 等为兼容 shim，仍支持：

```python
from auth import get_authenticated_client

email = "Yourname.Lastname25@student.xjtlu.edu.cn"
mail = get_authenticated_client(email)
items = mail.find_messages("inbox", sender="Registry", since="2026-05-29", unread_only=True, limit=20)
```

权威实现位于：

`.cursor/skills/xjtlu-owa-mail/scripts/xjtlu_owa_mail/`

## 功能一览

| 模块 | 能力 |
| --- | --- |
| `xjtlu-uim-login` | 外部包：HTTP 登录 UIM（412 时回退 jsdom）+ 可选 IdP |
| `xjtlu_owa_mail.uim_login` | 兼容入口，转调 `get_tgc` |
| `xjtlu_owa_mail.owa_auth` | 微软 SAML + KMSI → `session` + canary |
| `xjtlu_owa_mail.owa_mail` | `OWAMailClient`：搜索、正文、会话、附件、发信、回复/转发、标记/移动/删除 |
| `xjtlu_owa_mail.auth` | 三级认证缓存（OWA 会话 → TGC → UIM） |

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `XJTLU_USERNAME` | UIM 用户名（不含邮箱后缀） |
| `XJTLU_PASSWORD` | 密码 |
| `XJTLU_OTP_URL` | `otpauth://` TOTP |

`.env` / `.cache/` 已被 gitignore。请勿提交真实凭证。

## 仓库结构

```text
.
├── README.md
├── requirements.txt
├── .env.example
├── example.py                 # 转发到 skill 演示脚本
├── auth.py / owa_*.py …       # 兼容 shim → skill 包
├── .cursor-plugin/plugin.json # 可选：作为 Cursor 插件分发
└── .cursor/skills/xjtlu-owa-mail/
    ├── SKILL.md
    ├── scripts/
    │   ├── xjtlu_owa_mail/    # 权威 Python 包
    │   ├── example.py
    │   └── check_setup.py
    ├── references/
    └── assets/
```

## 说明

- 仅用于个人邮箱自动化学习，请遵守学校规定。
- 写操作在示例中默认注释；Agent 也应默认只读，除非用户明确要求。
- 若出现 `ProxyError` / `SSLError`，多为本地网络无法访问微软登录域名。
