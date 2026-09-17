"""OWA SSO：微软授权页（IE 兼容表单）+ UIM 登录 + KMSI。"""

from __future__ import annotations

import json
import re
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .log import log
from .uim_login import credentials, load_project_env, login as uim_login, otp_now

IE_UA = "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; Trident/4.0)"
OWA_HOME = "https://mail.xjtlu.edu.cn/owa/"


def _auto_submit(html: str, current_url: str):
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if form:
        action = form.get("action") or current_url
        data = {}
        for tag in form.find_all("input"):
            name = tag.get("name")
            if name:
                data[name] = tag.get("value") or ""
        return action, data

    match = re.search(r"\$Config\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not match:
        return None, None
    try:
        config = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None, None
    action = config.get("urlPost")
    if not action:
        return None, None
    data = {}
    if config.get("sFTName") and config.get("sFT"):
        data[config["sFTName"]] = config["sFT"]
    if config.get("sCtx"):
        data["ctx"] = config["sCtx"]
    canary_name = config.get("sCanaryTokenName") or "canary"
    if config.get("canary"):
        data[canary_name] = config["canary"]
    extra = config.get("oPostParams")
    if isinstance(extra, dict):
        data.update(extra)
    data["LoginOptions"] = "3"
    if config.get("sessionId"):
        data["hpgrequestid"] = config["sessionId"]
    return action, data


def _abs_url(action: str, current: str) -> str:
    if action.startswith("http"):
        return action.replace("&#x3a;", ":").replace("&#x2f;", "/")
    if action.startswith("/"):
        parsed = urlparse(current)
        return f"{parsed.scheme}://{parsed.netloc}{action}"
    return urljoin(current, action)


def _microsoft_saml_request(session: requests.Session, email_account: str) -> tuple[str, dict]:
    resp = session.get(OWA_HOME, allow_redirects=False, timeout=30)
    loc = resp.headers.get("Location")
    if not loc:
        raise RuntimeError("OWA 未返回微软登录跳转")
    loc += f"&login_hint={quote(email_account)}" if "?" in loc else f"?login_hint={quote(email_account)}"
    resp = session.get(loc, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form")
    if not form or not form.find("input", {"name": "SAMLRequest"}):
        raise RuntimeError("微软授权页未返回 SAMLRequest（IE 兼容表单）")
    action = form.get("action")
    data = {
        tag.get("name"): tag.get("value") or ""
        for tag in form.find_all("input")
        if tag.get("name")
    }
    if not action:
        raise RuntimeError("SAML 表单缺少 action")
    return action, data


def login_owa(email_account: str, uim_cookies: list[dict] | None = None):
    """
    完成 UIM + OWA SSO。
    返回 (requests.Session, canary, tgc, uim_cookies)。
    """
    if not email_account:
        raise ValueError("email_account 不能为空")
    load_project_env()
    username, password, otp_url = credentials()

    session = requests.Session()
    session.headers["User-Agent"] = IE_UA

    log("[owa] 正在向微软获取 SAMLRequest...")
    idp_action, idp_data = _microsoft_saml_request(session, email_account)

    skip_login = bool(uim_cookies and any(c.get("name") == "TGC" for c in uim_cookies))
    log("[owa] 正在登录 UIM 并提交 IdP...")
    result = uim_login(
        username,
        password,
        otp_now(otp_url),
        idp={"action": idp_action, "data": idp_data},
        cookies=uim_cookies,
        skip_login=skip_login,
    )
    tgc = result.get("tgc")
    uim_cookies_out = result.get("cookies") or []
    saml_html = result.get("samlHtml")
    if not saml_html:
        raise RuntimeError("UIM 登录未返回 SAMLResponse")

    action, data = _auto_submit(saml_html, idp_action)
    if not action or "SAMLResponse" not in data:
        raise RuntimeError("无法解析 IdP SAMLResponse 表单")

    log("[owa] 正在完成微软 SSO / KMSI...")
    resp = session.post(_abs_url(action, idp_action), data=data, timeout=30, allow_redirects=True)
    for _ in range(12):
        canary = session.cookies.get("X-OWA-CANARY")
        if canary:
            log(f"[owa] 成功登录 OWA，Canary: {canary[:10]}...")
            return session, canary, tgc, uim_cookies_out
        next_action, next_data = _auto_submit(resp.text, resp.url)
        if not next_action:
            break
        resp = session.post(
            _abs_url(next_action, resp.url),
            data=next_data,
            timeout=30,
            allow_redirects=True,
        )

    canary = session.cookies.get("X-OWA-CANARY")
    if not canary:
        raise RuntimeError(f"OWA SSO 未拿到 X-OWA-CANARY，当前 URL={resp.url}")
    return session, canary, tgc, uim_cookies_out


def get_owa_session(tgc_cookie: str, email_account: str):
    """
    兼容旧签名。有 TGC 时注入 cookie 并走同一套 SSO。
    """
    cookies = None
    if tgc_cookie:
        cookies = [{"name": "TGC", "value": tgc_cookie, "domain": ".uim.xjtlu.edu.cn", "path": "/"}]
    try:
        session, canary, _tgc, _cks = login_owa(email_account, uim_cookies=cookies)
        return session, canary
    except Exception as exc:
        log(f"[owa] 登录失败: {exc}")
        return None, None
