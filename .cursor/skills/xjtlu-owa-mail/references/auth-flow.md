# 认证与缓存流程

## 组件

| 模块 | 职责 |
| --- | --- |
| `xjtlu-uim-login`（外部包） | HTTP 登录 UIM（412 时回退 jsdom）+ 可选 IdP |
| `uim_login.py` | 兼容转调 `xjtlu_uim_login.get_tgc` |
| `owa_auth.py` | 微软 SAMLRequest（IE 兼容页）+ KMSI → `session` + `X-OWA-CANARY` |
| `auth.py` | 三级缓存回退，产出 `OWAMailClient` |

## 登录链路

1. 访问 `https://mail.xjtlu.edu.cn/owa/`，跟随跳转到微软登录。
2. 用 IE 兼容 UA 拿到含 `SAMLRequest` 的表单。
3. 调用 `xjtlu_uim_login.login(..., idp={action, data})` 完成学校 IdP，拿到 `samlHtml` / TGC。
4. 回投 `SAMLResponse`，完成微软 SSO / KMSI，直到 cookie 出现 `X-OWA-CANARY`。
5. 用 `session` + canary 构造 `OWAMailClient`，并以 `folder_stats("inbox")` 做可用性校验。

## 三级缓存

文件均在仓库工作目录下的 `.cache/`（权限 `0600`）：

1. **OWA 会话** `.cache/owa_session.json`  
   - 字段：`email_account`, `canary`, `cookies`, `updated_at`  
   - 重建 `requests.Session` 后调用 `folder_stats`；失败则进入下一步。

2. **TGC** `.cache/tgc.json`  
   - 字段：`tgc`, 可选 `cookies`, `updated_at`  
   - 用缓存 UIM cookie / TGC 调 `login_owa` 或 `get_owa_session`；成功则刷新 OWA 缓存。

3. **完整 UIM 登录**  
   - `login_owa(email)` → 写 TGC + OWA 缓存。

`force_refresh=True` 时跳过 1/2，直接走完整登录。

## 环境变量

由 `xjtlu_uim_login.load_project_env()` / `python-dotenv` 加载：

- `XJTLU_USERNAME`
- `XJTLU_PASSWORD`
- `XJTLU_OTP_URL`

模板见 `assets/env.example`。
