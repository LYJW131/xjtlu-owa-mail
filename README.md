# XJTLU OWA Mail

通过 XJTLU 统一身份认证（UIM）自动登录，获取 OWA 邮箱会话，实现命令行**读取**和**发送**邮件。

整个流程无需手动复制 Cookie：脚本会用账号密码 + OTP 自动完成 UIM 登录拿到 `TGC`，再走 SSO 换取 OWA 会话。

## 功能

- 自动 UIM 登录获取 `TGC` cookie（`uim_login.py`）
- 用 `TGC` 完成 OWA / Azure AD SSO，获取 `X-OWA-CANARY` 会话令牌（`owa_auth.py`）
- 读取收件箱最新邮件，支持获取完整正文（`owa_mail.py`）
- 通过 OWA 内部 API 发送邮件（`owa_mail.py`）

## 环境要求

- Python 3.12+
- 依赖见 `requirements.txt`

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置

复制示例文件并填入你的凭证：

```bash
cp .env.example .env
```

`.env` 字段说明：

| 变量 | 说明 |
| --- | --- |
| `XJTLU_USERNAME` | UIM 用户名（不含 `@student.xjtlu.edu.cn` 后缀） |
| `XJTLU_PASSWORD` | UIM 登录密码 |
| `XJTLU_OTP_URL` | 二次验证 OTP 地址，`otpauth://` 开头 |

> `.env` 已被 `.gitignore` 忽略，不会被提交。请勿将真实凭证写入代码或提交到仓库。

也可以不使用 `.env`，直接导出环境变量：

```bash
export XJTLU_USERNAME="Yourname.Lastname25"
export XJTLU_PASSWORD="your_password"
export XJTLU_OTP_URL="otpauth://totp/..."
```

## 运行

```bash
python3 main.py
```

默认会读取收件箱最新 5 封邮件并打印正文。发送邮件示例在 `main.py` 中默认注释，按需开启。

## 代码结构

| 文件 | 职责 |
| --- | --- |
| `main.py` | 程序入口，串联登录、读信、发信 |
| `uim_login.py` | UIM 统一身份认证登录，返回 `TGC` cookie |
| `owa_auth.py` | 用 `TGC` 完成 OWA/Azure AD SSO，返回会话与 Canary |
| `owa_mail.py` | OWA 邮件读取（`get_emails` / `get_email_body`）与发送（`send_email`） |

## 说明

- 本项目仅用于个人邮箱自动化学习用途，请遵守学校相关规定。
- 若运行时出现 `ProxyError` / `SSLError`，通常是本地代理或网络无法访问 `login.windows.net` 等微软登录域名，与代码逻辑无关。
