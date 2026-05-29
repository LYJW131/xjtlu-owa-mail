import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from owa_auth import get_owa_session
from owa_mail import send_email, get_emails
from uim_login import get_tgc_cookie


def get_authenticated_owa_session(email_account: str):
    """
    自动获取 TGC 并登录 OWA。
    """
    tgc = get_tgc_cookie()
    return get_owa_session(tgc, email_account)

if __name__ == "__main__":
    print("=== 开始初始化 OWA 客户端 ===")

    # 获取认证会话和Token
    email_account = f"{os.environ.get("XJTLU_USERNAME")}@student.xjtlu.edu.cn"
    session, canary = get_authenticated_owa_session(email_account)
    
    if session and canary:
        # ==========================================
        # 1. 读取邮件示例
        # ==========================================
        print("\n=== 测试：读取最新邮件（含正文） ===")
        get_emails(session, canary, limit=5, with_body=True)
        
        # ==========================================
        # 2. 发送邮件示例 (如需测试请取消下述注释)
        # ==========================================
        # print("\n=== 测试：发送邮件 ===")
        # subject = "Python API测试发信 - 模块化版本"
        # body = "这是一封由重构后的 Python 脚本（模块化格式）自动发送的测试邮件！"
        # send_email(session, canary, email_account, subject, body)
        
    else:
        print("\n[-] 进程终止：未获取到有效的 Session 或 Canary Token。")
