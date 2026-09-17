# 约束与排障

## 硬约束

- 个人学习/自动化用途；遵守学校 IT 与邮箱使用规定。
- 禁止把 `.env`、`.cache/`、真实密码、OTP secret、TGC、Cookie 提交到 git 或贴进公开对话。
- Agent 默认只读；发信 / 删除 / 移动 / 标记等写操作需用户明确确认后再执行。
- 不要在本仓库内重新实现瑞数绕过；委托 [`xjtlu-uim-login`](https://github.com/LYJW131/xjtlu-uim-login)。

## UIM / 瑞数（摘要）

- 当前瑞数按 User-Agent 分流：默认 HTTP `requests` 走 `doLogin`，412 时回退 jsdom。
- 含 `darwin` / `okhttp` 等子串或手机 WebKit 的 UA 可能直接放行（细节以外部包 README 为准）。
- 浏览器 XHR 会带 `KgdICDMu`；页面 `/sso-mfa/rest/ueba/send` 只服务浏览器 UI，JSON `doLogin` 不依赖它。

## 常见错误

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| `ProxyError` / `SSLError` | 本地网络到微软登录域不通 | 换网络/关错误代理；非代码逻辑问题 |
| 认证失败 / 无 canary | 凭证错误、OTP 失效、缓存脏 | 检查 `.env`；删 `.cache/` 或 `force_refresh=True` |
| 缺少依赖 | 未装 requirements | `pip install -r assets/requirements.txt` |
| 412 + jsdom | HTTP 路径被瑞数拦截 | 安装 Node.js 18+，让外部包自动 `npm install jsdom` |
| `find_messages` 空结果 | 条件过严或文件夹别名不对 | 放宽 `since`/发件人；确认 `inbox` 等别名 |

## 安全注意

- 缓存文件仅本地使用；多账号切换时确认 `email_account` 匹配，避免串会话。
- 示例脚本中的写操作必须保持注释，直到用户要求开启。
