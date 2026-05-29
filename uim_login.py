"""
UIM 登录脚本（最小实现）
通过 RSA 加密密码完成 UIM 统一身份认证登录，返回 TGC cookie。
"""
import os
import base64
from urllib.parse import urlparse, parse_qs, urlencode

import requests
import pyotp
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

UIM_BASE_URL = "https://uim.xjtlu.edu.cn"
UIM_AUTH_POLICY_API = f"{UIM_BASE_URL}/esc-sso/api/v3/auth/policy"
UIM_DO_LOGIN_API = f"{UIM_BASE_URL}/esc-sso/api/v3/auth/doLogin"
UIM_OAUTH2_AUTHORIZE_API = f"{UIM_BASE_URL}/esc-sso/oauth2.0/authorize"
UIM_NGW_LOGIN_API = f"{UIM_BASE_URL}/ngw/login"
OAUTH2_CLIENT_ID = "fab04-6690-39830"

COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
}


def _get_env_credentials() -> tuple[str, str, str]:
    username = os.environ.get("XJTLU_USERNAME")
    password = os.environ.get("XJTLU_PASSWORD")
    otp_url = os.environ.get("XJTLU_OTP_URL")

    if not username:
        raise ValueError("环境变量 XJTLU_USERNAME 未设置")
    if not password:
        raise ValueError("环境变量 XJTLU_PASSWORD 未设置")
    if not otp_url:
        raise ValueError("环境变量 XJTLU_OTP_URL 未设置")

    return username, password, otp_url


def _generate_otp(otp_url: str) -> str:
    secret = parse_qs(urlparse(otp_url).query).get('secret', [None])[0]
    if not secret:
        raise ValueError("OTP URL 中缺少 secret 参数")
    return pyotp.TOTP(secret).now()


def _encrypt_password(password: str, public_key_content: str) -> str:
    pem_key = f"-----BEGIN PUBLIC KEY-----\n{public_key_content}\n-----END PUBLIC KEY-----"
    public_key = serialization.load_pem_public_key(
        pem_key.encode('utf-8'), backend=default_backend()
    )
    encrypted = public_key.encrypt(password.encode('utf-8'), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode('utf-8')


def get_tgc_cookie() -> str:
    """
    执行完整 UIM 登录流程并返回 TGC cookie 字符串。
    """
    username, password, otp_url = _get_env_credentials()
    session = requests.Session()
    session.headers.update(COMMON_HEADERS)

    # 1. 获取认证策略（公钥）
    data = session.get(UIM_AUTH_POLICY_API).json()
    if str(data.get("code")) != "0":
        raise RuntimeError(f"获取认证策略失败: {data.get('msg')}")
    param = data.get("data", {}).get("param", {})
    public_key = param.get("publicKey")
    public_key_id = param.get("publicKeyId")
    if not public_key or not public_key_id:
        raise RuntimeError("响应中缺少公钥信息")

    # 2. 加密密码并登录
    payload = {
        "authType": "webLocalAuth",
        "dataField": {
            "username": username,
            "password": _encrypt_password(password, public_key),
            "publicKeyId": public_key_id,
        },
    }
    result = session.post(UIM_DO_LOGIN_API, json=payload).json()

    # 3. 如需二次验证（MFA），执行 OTP 登录
    if "mfaLogin" in result.get("data", {}).get("redirect", ""):
        otp_payload = {
            "authType": "webOtpAuth",
            "dataField": {"username": username, "password": "", "otp": _generate_otp(otp_url)},
            "redirectUri": "",
        }
        result = session.post(UIM_DO_LOGIN_API, json=otp_payload).json()

    if str(result.get("code")) != "0":
        raise RuntimeError(f"登录失败，错误码: {result.get('code')}")

    # 4. 获取 OAuth2 授权码
    oauth_url = f"{UIM_OAUTH2_AUTHORIZE_API}?" + urlencode({
        'response_type': 'code',
        'client_id': OAUTH2_CLIENT_ID,
        'redirect_uri': UIM_NGW_LOGIN_API,
    })
    resp = session.get(oauth_url, allow_redirects=False)
    code = parse_qs(urlparse(resp.headers.get('Location', '')).query).get('code', [None])[0]
    if not code:
        raise RuntimeError("未能获取 OAuth2 授权码")

    # 5. 用授权码换取最终 cookies（写入 session）
    session.get(f"{UIM_NGW_LOGIN_API}?code={code}", allow_redirects=False)

    tgc = session.cookies.get("TGC")
    if not tgc:
        raise RuntimeError("登录成功但未获取到 TGC cookie")
    return tgc


if __name__ == "__main__":
    print(get_tgc_cookie())
