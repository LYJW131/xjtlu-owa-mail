"""
认证与缓存模块。

双层缓存机制：
1) 优先复用 OWA 会话缓存（session cookies + canary）
2) OWA 失效时，尝试使用缓存 TGC 重新登录 OWA
3) TGC 失效时，回退到完整 UIM 登录获取新 TGC
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from owa_auth import get_owa_session, login_owa
from owa_mail import OWAMailClient
from xjtlu_uim_login import load_project_env

CACHE_DIR = Path(".cache")
OWA_CACHE_FILE = CACHE_DIR / "owa_session.json"
TGC_CACHE_FILE = CACHE_DIR / "tgc.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(path, 0o600)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _serialize_cookies(session: requests.Session) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in session.cookies:
        out.append(
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path or "/",
                "secure": bool(c.secure),
                "expires": c.expires,
            }
        )
    return out


def _rebuild_session(cookies: list[dict[str, Any]]) -> requests.Session:
    session = requests.Session()
    for item in cookies:
        name = item.get("name")
        value = item.get("value")
        domain = item.get("domain")
        if not name or value is None:
            continue
        kwargs: dict[str, Any] = {}
        if domain:
            kwargs["domain"] = domain
        if item.get("path"):
            kwargs["path"] = item.get("path")
        session.cookies.set(name, value, **kwargs)
    return session


def _save_owa_cache(email_account: str, session: requests.Session, canary: str) -> None:
    payload = {
        "email_account": email_account,
        "canary": canary,
        "cookies": _serialize_cookies(session),
        "updated_at": _utc_now_iso(),
    }
    _save_json(OWA_CACHE_FILE, payload)


def _save_tgc_cache(tgc: str, cookies: list[dict[str, Any]] | None = None) -> None:
    payload: dict[str, Any] = {"tgc": tgc, "updated_at": _utc_now_iso()}
    if cookies:
        payload["cookies"] = cookies
    _save_json(TGC_CACHE_FILE, payload)


def _validate_owa(session: requests.Session, canary: str) -> OWAMailClient | None:
    try:
        client = OWAMailClient(session, canary)
        stats = client.folder_stats("inbox")
        if stats is None:
            return None
        return client
    except Exception:
        return None


def _load_owa_client_from_cache(email_account: str) -> OWAMailClient | None:
    data = _load_json(OWA_CACHE_FILE)
    if not data:
        return None
    if data.get("email_account") != email_account:
        return None
    canary = data.get("canary")
    cookies = data.get("cookies")
    if not canary or not isinstance(cookies, list):
        return None
    session = _rebuild_session(cookies)
    return _validate_owa(session, canary)


def _try_login_with_cached_tgc(email_account: str) -> OWAMailClient | None:
    data = _load_json(TGC_CACHE_FILE)
    if not data:
        return None
    tgc = data.get("tgc")
    if not tgc:
        return None
    try:
        uim_cookies = data.get("cookies")
        if isinstance(uim_cookies, list) and uim_cookies:
            session, canary, _tgc, _cks = login_owa(email_account, uim_cookies=uim_cookies)
        else:
            session, canary = get_owa_session(tgc, email_account)
    except Exception as exc:
        print(f"[-] 缓存 TGC 重登 OWA 异常: {exc}")
        return None
    if not session or not canary:
        print("[-] 缓存 TGC 已失效或 OWA 会话建立失败，将回退至 UIM 完整登录")
        return None
    client = _validate_owa(session, canary)
    if not client:
        return None
    _save_owa_cache(email_account, session, canary)
    return client


def _try_get_owa_session(tgc: str, email_account: str, retries: int = 2):
    """调用 get_owa_session，失败时最多重试 retries 次，每次记录原因。"""
    for attempt in range(1, retries + 1):
        try:
            session, canary = get_owa_session(tgc, email_account)
            if session and canary:
                return session, canary
            print(f"[-] OWA 会话登录未返回 canary（第 {attempt}/{retries} 次）")
        except Exception as exc:
            print(f"[-] OWA 会话登录异常（第 {attempt}/{retries} 次）: {exc}")
        if attempt < retries:
            time.sleep(2)
    return None, None


def _fresh_login(email_account: str) -> OWAMailClient | None:
    try:
        session, canary, tgc, uim_cookies = login_owa(email_account)
    except Exception as exc:
        print(f"[-] UIM/OWA 登录失败: {exc}")
        return None
    if not session or not canary:
        print("[-] 登录未返回 OWA 会话")
        return None
    if tgc:
        _save_tgc_cache(tgc, uim_cookies or None)
    client = _validate_owa(session, canary)
    if not client:
        print("[-] OWA 会话验证失败（folder_stats 返回 None）")
        return None
    _save_owa_cache(email_account, session, canary)
    return client


def get_authenticated_client(
    email_account: str,
    *,
    force_refresh: bool = False,
) -> OWAMailClient | None:
    """
    获取可用 OWA 客户端（带双层缓存回退）。

    :param email_account: 完整邮箱地址，如 xxx@student.xjtlu.edu.cn
    :param force_refresh: True 时跳过缓存，直接走 UIM 完整登录
    """
    if not email_account:
        raise ValueError("email_account 不能为空")
    load_project_env()

    if not force_refresh:
        client = _load_owa_client_from_cache(email_account)
        if client:
            print("[+] 使用缓存 OWA 会话登录成功")
            return client

        client = _try_login_with_cached_tgc(email_account)
        if client:
            print("[+] OWA 会话已过期，使用缓存 TGC 重登成功")
            return client

    client = _fresh_login(email_account)
    if client:
        print("[+] 缓存不可用，已通过 UIM 完整登录并刷新缓存")
    return client

