import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
import re

def get_owa_session(tgc_cookie: str, email_account: str):
    """
    统一的认证函数，通过TGC登录获取OWA的Session和Canary Token
    
    :param tgc_cookie: 身份验证用的 TGC Cookie
    :param email_account: 登录账号（邮箱地址）
    :return: (requests.Session, str) Session对象和Canary Token
    """
    session = requests.Session()
    # 注入UIM身份验证Cookie
    session.cookies.set("TGC", tgc_cookie, domain=".uim.xjtlu.edu.cn")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }

    def auto_submit_form(html, current_url):
        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form')
        if form:
            action = form.get('action') or current_url
            data = {}
            for input_tag in form.find_all('input'):
                name = input_tag.get('name')
                if name:
                    data[name] = input_tag.get('value', '').replace('&#x3d;', '=').replace('&amp;', '&')
            return action, data

        # 尝试匹配Azure AD的KMSI (保持登录) 页面的隐藏JSON拦截器
        match = re.search(r'\$Config\s*=\s*(\{.*?\});', html, re.DOTALL)
        if match:
            try:
                config = json.loads(match.group(1))
                action = config.get('urlPost')
                if action:
                    data = {}
                    if 'sFTName' in config and 'sFT' in config: data[config['sFTName']] = config['sFT']
                    if 'sCtx' in config: data['ctx'] = config['sCtx']
                    if 'sCanaryTokenName' in config and 'canary' in config: data[config['sCanaryTokenName']] = config['canary']
                    data['LoginOptions'] = '3' # 拒绝保持登录状态即可继续
                    data['hpgrequestid'] = config.get('sessionId', '')
                    return action, data
            except Exception:
                pass
        return None, None

    print("[*] 正在登录 OWA 获取 Canary Token...")
    resp = session.get("https://mail.xjtlu.edu.cn/owa/", headers=headers, allow_redirects=False)
    
    if 'Location' in resp.headers:
        loc = resp.headers['Location']
        # 添加 login_hint 告诉微软我们的账号，从而直接触发跳转去学校机构的SSO
        loc += f"&login_hint={urllib.parse.quote(email_account)}" if '?' in loc else f"?login_hint={urllib.parse.quote(email_account)}"
        resp = session.get(loc, headers=headers)
        
        # 循环处理所有的SAML自动提交表单 (Azure AD <-> UIM)
        for _ in range(10):
            action, data = auto_submit_form(resp.text, resp.url)
            if not action: 
                break
            
            # 处理相对路径
            if action.startswith('/'):
                parsed = urllib.parse.urlparse(resp.url)
                action = f"{parsed.scheme}://{parsed.netloc}{action}"
            elif not action.startswith('http'):
                action = resp.url
                
            action = action.replace('&#x3a;', ':').replace('&#x2f;', '/')
            resp = session.post(action, data=data, headers=headers, allow_redirects=True)

    # 提取防CSRF的Canary Token，这是发件/读信核心凭证
    canary = session.cookies.get("X-OWA-CANARY")
    if not canary:
        print("[-] 登录失败，未能获取到 X-OWA-CANARY Cookie！")
        return None, None
        
    print(f"[+] 成功登录！获取到 Canary: {canary[:10]}...")
    return session, canary
