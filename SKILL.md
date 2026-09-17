---
name: xjtlu-owa-mail
description: 读取、搜索、发送、回复、转发和管理西浦（XJTLU）学生/教职工 OWA 邮箱（mail.xjtlu.edu.cn）的邮件，自动完成 UIM 统一身份认证 + 微软 SSO 登录并缓存会话。当用户提到西浦邮箱、学校邮件、OWA、Outlook Web、UIM、"看看有没有新邮件"、"帮我给老师/Registry/同学发邮件"、"找一下 xx 发来的邮件/附件"、"回复这封邮件"等任何涉及 xjtlu.edu.cn 邮箱的读写需求时使用本 skill，即使用户没有明确说"OWA"。
license: MIT
compatibility: Requires Python 3.10+ and network access to uim.xjtlu.edu.cn, login.microsoftonline.com and mail.xjtlu.edu.cn; Node.js 18+ only if the UIM WAF starts challenging (jsdom fallback). Credentials come from a local .env, never from the conversation.
metadata:
  author: LYJW131
  version: "0.2.0"
  repository: https://github.com/LYJW131/xjtlu-owa-mail
---

# XJTLU OWA Mail

通过 `scripts/owa` 命令行操作西浦 OWA 邮箱。每个子命令都把结果以 **JSON 写到 stdout**，进度日志写到 stderr，直接用 Bash 调用即可，不需要写 Python。

## 调用方式

```bash
# SKILL_DIR 是本 SKILL.md 所在目录（Claude Code 里可直接用 ${CLAUDE_SKILL_DIR}）；
# 首次运行会自动创建 .venv 并安装依赖
"$SKILL_DIR/scripts/owa" <子命令> [参数...]
```

下文示例里的 `owa` 都指 `"$SKILL_DIR/scripts/owa"`。

前置条件：`$SKILL_DIR/.env` 中有 `XJTLU_USERNAME` / `XJTLU_PASSWORD` / `XJTLU_OTP_URL`（见 `.env.example`）。凭据缺失时命令会返回 `{"ok": false, "error": "环境变量 XJTLU_USERNAME 未设置"}`，此时请用户填好 `.env`，不要替用户猜密码。

登录是自动的：先用缓存的 OWA 会话，失效再用缓存 TGC，再失效才走完整 UIM 登录（HTTP，约 5–10 秒）。不必单独先执行 `login`，除非想验证凭据或强制刷新（`login --force`）。

## 常用工作流

### 看新邮件 / 找邮件

```bash
owa stats                                             # 收件箱总数与未读数
owa search --unread --limit 10                        # 未读
owa search --sender Registry --since 2026-09-01       # 某发件人、某日期起
owa search --subject "timetable" --has-attachments    # 主题含关键词且带附件
owa search --folder sent --limit 5                    # 已发送
```

`search` 返回 `messages[]`，每项含 `item_id`（后续操作都靠它）、`subject`、`sender`、`sender_email`、`received`、`is_read`、`has_attachments`、`preview`。筛选在服务端完成，`--sender/--subject/--body` 是不区分大小写的子串匹配。文件夹别名：`inbox` `sent` `drafts` `deleted` `junk` `archive`，也可写自定义文件夹的显示名。

### 读正文 / 附件

```bash
owa read "<item_id>"                    # 纯文本正文（默认截到 20000 字符，--max-chars 0 不截断）
owa read "<item_id>" --html             # HTML 正文
owa thread "<item_id>"                  # 同一会话的邮件列表
owa attachments "<item_id>"             # 附件元数据
owa download "<item_id>" --out ./downloads   # 下载全部非内嵌附件，返回保存路径
```

`item_id` 含 `/` `+` `=`，在 shell 里一定要加引号。

### 发信 / 回复 / 转发

```bash
owa send --to a@xjtlu.edu.cn --subject "关于..." --body $'第一段\n\n第二段'
owa send --to a@x --to b@x --cc c@x --subject S --body-file ./draft.txt --attach ./file.pdf
printf '正文' | owa send --to a@x --subject S            # 正文也可从 stdin 传
owa send --to a@x --subject S --body ... --draft        # 只存草稿，不发送
owa reply "<item_id>" --body "收到，谢谢" [--all]
owa forward "<item_id>" --to a@x --body "请查收"
```

**正文格式规则（重要）**：默认 `auto`——正文含 HTML 标签就按 HTML 发送，否则按纯文本发送，换行和缩进原样保留。想要富文本就直接写 HTML（`<p>`、`<ul>`、`<b>` 等）；不要为了换行手写 `<br>` 混在纯文本里。`--html` 强制按 HTML（纯文本会自动转成 `<p>/<br>`），`--text` 强制纯文本。中文 OWA 会给回复/转发自动加 `答复:` / `转发:` 前缀。

发信前请把收件人、主题、正文完整展示给用户确认，发出去就撤不回；用户明确要求发送后再执行。

### 管理

```bash
owa mark-read "<id>" ["<id2>" ...]        # --unread 标记未读
owa flag "<id>"                            # --clear 清除旗标
owa move "<id>" --to archive
owa delete "<id>"                          # 移到已删除邮件；--hard 永久删除（需用户明确要求）
owa categorize "<id>" --category "重要"
```

## 输出约定

- 成功：`{"ok": true, ...}`；失败：`{"ok": false, "error": "..."}` 且退出码 1。
- 默认缩进 JSON；加全局 `--compact` 输出单行。
- 设置环境变量 `XJTLU_OWA_QUIET=1` 可关掉本项目的 stderr 进度日志（登录包自身的少量 `[http] ...` 输出仍会出现在 stderr，不影响 stdout JSON）。
- `--account` 可覆盖默认邮箱（默认 `XJTLU_EMAIL`，否则 `XJTLU_USERNAME@student.xjtlu.edu.cn`）。

## 排错

| 现象 | 处理 |
| --- | --- |
| `环境变量 XJTLU_* 未设置` | 让用户填 `$SKILL_DIR/.env` |
| `UIM 登录失败: ... ` | 密码或 OTP 错误，让用户核对；OTP 依赖本机时间准确 |
| `HTTP 412 / 瑞数挑战页` | UIM 的 WAF 规则变了，登录包会自动回退 jsdom（需要 Node.js 18+）；仍失败就告诉用户需要更新 `xjtlu-uim-login` |
| `ProxyError` / `SSLError` | 本机网络无法访问微软登录域名，与代码无关 |
| `read` 返回 `邮件不存在` | `item_id` 已失效（邮件被移动/删除），重新 `search` |

想直接在 Python 里用库（`OWAMailClient`）或了解 EWS JSON 细节，读 [references/api.md](references/api.md)。
