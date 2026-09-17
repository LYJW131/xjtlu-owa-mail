# XJTLU OWA Mail

西浦（XJTLU）OWA 邮箱自动化：自动完成 UIM 统一身份认证 + 微软 SSO，然后通过 OWA 内部 `service.svc`（EWS JSON）读信、搜信、发信、回复、转发和管理邮件。

同时是一个标准的 **Agent Skill**（仓库根目录即 skill 目录，含 `SKILL.md` + `scripts/owa` CLI），智能体直接用 Bash 调用，结果为 JSON。

```
xjtlu-owa-mail/
├── SKILL.md               # 给智能体看的使用说明（触发条件、子命令、格式规则、排错）
├── scripts/
│   ├── owa                # CLI 入口：自动准备 .venv 并转调 owa_cli.py
│   └── owa_cli.py         # 子命令实现，stdout 只输出 JSON，日志走 stderr
├── references/api.md      # Python 库 API、EWS JSON 方言、登录链路
├── AGENTS.md              # 给其他 agent / 维护者的仓库约定
├── .claude-plugin/        # plugin.json + marketplace.json（/plugin marketplace add 用）
├── xjtlu_owa_mail/        # Python 包
│   ├── auth.py            #   三级认证缓存（OWA 会话 → TGC → UIM 完整登录）
│   ├── owa_auth.py        #   微软 SAMLRequest → 学校 IdP → KMSI → X-OWA-CANARY
│   ├── owa_mail.py        #   OWAMailClient（搜索/正文/附件/发信/回复/转发/管理）
│   ├── uim_login.py       #   薄封装：转调独立包 xjtlu-uim-login，补 email_account()
│   └── log.py             #   stderr 日志
├── example.py             # 库用法示例
├── requirements.txt / pyproject.toml
├── LICENSE                # MIT
└── .env.example
```

UIM 登录逻辑单独维护在 [`xjtlu-uim-login`](https://github.com/LYJW131/xjtlu-uim-login)：当前瑞数 WAF 按 User-Agent 分流，UA 含 `darwin` 等子串即放行，默认走纯 HTTP `doLogin`，遇 412 才回退 jsdom。

## 安装

### 作为 Agent Skill（推荐）

仓库根目录就是 skill 目录（`SKILL.md` + `scripts/` + `references/`），符合 [Agent Skills 规范](https://agentskills.io/specification)，Claude Code / Codex / Cursor / OpenCode 等都能用。

```bash
# 方式一：skills CLI，一条命令装到所有已安装的 agent（-g 为全局）
npx skills add LYJW131/xjtlu-owa-mail -g

# 方式二：Claude Code 插件市场
/plugin marketplace add LYJW131/xjtlu-owa-mail
/plugin install xjtlu-owa-mail@xjtlu-owa-mail

# 方式三：直接 clone 到个人 skills 目录
git clone https://github.com/LYJW131/xjtlu-owa-mail.git ~/.claude/skills/xjtlu-owa-mail

# 方式四：本地开发时软链
ln -s "$(pwd)" ~/.claude/skills/xjtlu-owa-mail
```

装好后在 skill 目录里放 `.env`（`cp .env.example .env` 后填账号），首次调用 `scripts/owa` 会自动创建 `.venv` 并安装依赖。

### 作为普通 Python 项目

```bash
git clone https://github.com/LYJW131/xjtlu-owa-mail.git
cd xjtlu-owa-mail
cp .env.example .env        # 填 XJTLU_USERNAME / XJTLU_PASSWORD / XJTLU_OTP_URL
scripts/owa login           # 自动建 .venv、装依赖并验证登录
```

环境要求：Python 3.10+；Node.js 18+ 仅在 UIM 回退 jsdom 时需要。

## CLI 用法

```bash
scripts/owa stats                                        # 收件箱总数 / 未读
scripts/owa search --unread --limit 10                   # 未读邮件
scripts/owa search --sender Registry --since 2026-09-01  # 按发件人 + 日期
scripts/owa read "<item_id>"                             # 纯文本正文（--html 取 HTML）
scripts/owa download "<item_id>" --out ./downloads       # 下载附件
scripts/owa send --to a@xjtlu.edu.cn --subject "S" --body $'第一行\n第二行' --attach ./f.pdf
scripts/owa reply "<item_id>" --body "收到" --all
scripts/owa forward "<item_id>" --to b@xjtlu.edu.cn
scripts/owa mark-read / flag / move / delete / categorize "<item_id>" ...
```

全部子命令见 `scripts/owa --help`。输出约定：成功 `{"ok": true, ...}`，失败 `{"ok": false, "error": "..."}` 且退出码 1；`--compact` 单行输出；`XJTLU_OWA_QUIET=1` 关闭 stderr 日志。

### 正文格式

`send` / `reply` / `forward` 默认 `auto`：正文含 HTML 标签按 HTML 发送，否则按纯文本发送，换行与缩进原样保留。`--html` 强制 HTML（纯文本自动转成 `<p>` / `<br>`），`--text` 强制纯文本。此前默认把纯文本按 HTML 发导致换行被折叠的问题已修复。

## Python 库

```python
from xjtlu_owa_mail import get_authenticated_client, email_account

mail = get_authenticated_client(email_account())
for m in mail.find_messages("inbox", sender="Registry", since="2026-09-01", unread_only=True, limit=20):
    print(m.received, m.sender, m.subject)

detail = mail.get_message(m.item_id, body_type="Text")
mail.send_message("someone@xjtlu.edu.cn", "主题", "第一行\n第二行")
```

完整 API 与 EWS 细节见 [references/api.md](references/api.md)。

## 配置

| 变量 | 说明 |
| --- | --- |
| `XJTLU_USERNAME` | UIM 用户名（不含 `@student.xjtlu.edu.cn`） |
| `XJTLU_PASSWORD` | UIM 登录密码 |
| `XJTLU_OTP_URL` | OTP 地址，`otpauth://` 开头 |
| `XJTLU_EMAIL` | 可选，完整邮箱（非 student 域时填写） |
| `XJTLU_OWA_CACHE_DIR` | 可选，认证缓存目录（默认仓库下 `.cache/`） |

`.env` 从当前工作目录向上查找，找不到再读仓库根目录；缓存文件 `0600` 权限且已被 `.gitignore` 忽略。

## 开发

```bash
skills-ref validate "$(pwd)"       # Agent Skills 规范校验（要传绝对路径，目录名须等于 skill name）
claude plugin validate . --strict  # Claude Code 插件清单校验
```

版本号需同时更新 `SKILL.md`（`metadata.version`）、`pyproject.toml`、`.claude-plugin/plugin.json`。

## 说明

- 本项目仅用于个人邮箱自动化学习用途，请遵守学校相关规定。
- 筛选条件通过 EWS `Restriction` 在服务端执行（已在 XJTLU OWA 实测验证 JSON 方言）。
- 若出现 `ProxyError` / `SSLError`，多为本地网络无法访问微软登录域名，与代码逻辑无关。
