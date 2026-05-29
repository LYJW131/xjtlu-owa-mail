"""
OWA 邮件操作模块
通过 OWA 内部 service.svc API 实现邮件的发送与读取。
"""

SERVICE_URL = "https://mail.xjtlu.edu.cn/owa/service.svc"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"

# 所有请求共用的 EWS 请求头块（时区等上下文）
REQUEST_HEADER = {
    "__type": "JsonRequestHeaders:#Exchange",
    "RequestServerVersion": "Exchange2013",
    "TimeZoneContext": {
        "__type": "TimeZoneContext:#Exchange",
        "TimeZoneDefinition": {
            "__type": "TimeZoneDefinitionType:#Exchange",
            "Id": "China Standard Time"
        }
    }
}


def _build_headers(action: str, canary: str) -> dict:
    """构造 OWA service.svc 请求所需的 HTTP 头。"""
    return {
        "X-Requested-With": "XMLHttpRequest",
        "Action": action,
        "Content-Type": "application/json; charset=utf-8",
        "X-OWA-CANARY": canary,
        "User-Agent": USER_AGENT,
    }


def _post(session, canary: str, action: str, body: dict, request_type: str):
    """
    向 OWA service.svc 发送一个 action 请求。

    :return: 成功返回解析后的 JSON dict，失败返回 None
    """
    url = f"{SERVICE_URL}?action={action}&app=Mail"
    payload = {
        "__type": f"{request_type}:#Exchange",
        "Header": REQUEST_HEADER,
        "Body": body,
    }

    res = session.post(url, headers=_build_headers(action, canary), json=payload)
    if res.status_code != 200:
        print(f"[-] {action} 请求失败，HTTP状态码：{res.status_code}")
        return None

    return res.json()


def send_email(session, canary: str, to_email: str, subject: str, body_html: str) -> bool:
    """
    通过 OWA 内部 API 直接发送邮件

    :param session: 包含登录态的 requests.Session 实例
    :param canary: OWA 的防 CSRF 令牌
    :param to_email: 收件人邮箱
    :param subject: 邮件主题
    :param body_html: 邮件 HTML 正文
    :return: 发送是否成功
    """
    if not session or not canary:
        print("[-] 缺乏有效的会话或认证 Token，无法发送邮件。")
        return False

    print("[*] 正在发送邮件...")
    body = {
        "__type": "CreateItemRequest:#Exchange",
        "Items": [
            {
                "__type": "Message:#Exchange",
                "Subject": subject,
                "Body": {
                    "__type": "BodyContentType:#Exchange",
                    "BodyType": "HTML",
                    "Value": body_html
                },
                "ToRecipients": [
                    {
                        "__type": "EmailAddress:#Exchange",
                        "RoutingType": "SMTP",
                        "EmailAddress": to_email,
                        "Name": ""
                    }
                ]
            }
        ],
        "MessageDisposition": "SendAndSaveCopy"
    }

    resp_data = _post(session, canary, "CreateItem", body, "CreateItemJsonRequest")
    if resp_data is None:
        return False

    try:
        response_code = resp_data['Body']['ResponseMessages']['Items'][0]['ResponseCode']
    except (KeyError, IndexError):
        print("[-] 解析API返回结果失败：", resp_data)
        return False

    if response_code == "NoError":
        print("[+] 邮件发送成功！")
        return True

    print("[-] 邮件发送失败，API返回：", response_code)
    return False


def get_email_body(session, canary: str, item_id: str, body_type: str = "Text") -> str:
    """
    通过 ItemId 获取单封邮件的完整正文

    :param session: 包含登录态的 requests.Session 实例
    :param canary: OWA 的防 CSRF 令牌
    :param item_id: 邮件的 ItemId
    :param body_type: 正文类型，"Text"（纯文本）或 "HTML"
    :return: 邮件正文字符串，失败返回空字符串
    """
    if not session or not canary:
        print("[-] 缺乏有效的会话或认证 Token，无法读取正文。")
        return ""

    body = {
        "__type": "GetItemRequest:#Exchange",
        "ItemShape": {
            "__type": "ItemResponseShape:#Exchange",
            "BaseShape": "AllProperties",
            "BodyType": body_type,
            "FilterHtmlContent": False,
            "AddBlankTargetToLinks": False,
            "MaximumBodySize": 2097152
        },
        "ItemIds": [
            {
                "__type": "ItemId:#Exchange",
                "Id": item_id
            }
        ]
    }

    resp_data = _post(session, canary, "GetItem", body, "GetItemJsonRequest")
    if resp_data is None:
        return ""

    try:
        item = resp_data['Body']['ResponseMessages']['Items'][0]['Items'][0]
        body_field = item.get('NormalizedBody') or item.get('Body') or {}
        return body_field.get('Value', '')
    except (KeyError, IndexError, TypeError) as e:
        print(f"[-] 解析正文失败：{e}")
        return ""


def get_emails(session, canary: str, limit: int = 5, with_body: bool = False) -> bool:
    """
    读取收件箱中的最新邮件

    :param session: 包含登录态的 requests.Session 实例
    :param canary: OWA 的防 CSRF 令牌
    :param limit: 获取邮件的数量限制
    :param with_body: 是否额外获取并打印每封邮件的完整正文
    :return: 获取是否成功
    """
    if not session or not canary:
        print("[-] 缺乏有效的会话或认证 Token，无法读取邮件。")
        return False

    print(f"[*] 正在获取收件箱最新 {limit} 封邮件...")
    body = {
        "__type": "FindItemRequest:#Exchange",
        "ItemShape": {
            "__type": "ItemResponseShape:#Exchange",
            "BaseShape": "IdOnly"
        },
        "ParentFolderIds": [
            {
                "__type": "DistinguishedFolderId:#Exchange",
                "Id": "inbox"
            }
        ],
        "Traversal": "Shallow",
        "Paging": {
            "__type": "IndexedPageView:#Exchange",
            "BasePoint": "Beginning",
            "Offset": 0,
            "MaxEntriesReturned": limit
        },
        "ViewFilter": "All",
        "ClutterFilter": "All",
        "ShapeName": "MailListItem",
        "SortOrder": [
            {
                "__type": "SortResults:#Exchange",
                "Order": "Descending",
                "Path": {
                    "__type": "PropertyUri:#Exchange",
                    "FieldURI": "DateTimeReceived"
                }
            }
        ]
    }

    resp_data = _post(session, canary, "FindItem", body, "FindItemJsonRequest")
    if resp_data is None:
        return False

    try:
        items = resp_data['Body']['ResponseMessages']['Items'][0]['RootFolder']['Items']
    except (KeyError, IndexError) as e:
        print("[-] 解析API返回结果失败（可能是空收件箱或格式不同）：", e)
        return False

    print(f"[+] 成功获取 {len(items)} 封邮件：\n")
    for i, item in enumerate(items, 1):
        subject = item.get('Subject', '无主题')
        mailbox = item.get('From', {}).get('Mailbox', {})
        sender = mailbox.get('Name', '未知发件人')
        sender_email = mailbox.get('EmailAddress', '')
        received_time = item.get('DateTimeReceived', '未知时间')

        print(f"[{i}] 发件人: {sender} ({sender_email})")
        print(f"    时间: {received_time}")
        print(f"    主题: {subject}")

        if with_body:
            item_id = item.get('ItemId', {}).get('Id', '')
            if item_id:
                email_body = get_email_body(session, canary, item_id)
                print(f"    正文:\n{email_body.strip()}")
            else:
                print("    正文: [未获取到 ItemId]")
            print("-" * 60)
        else:
            preview = item.get('Preview', '无预览').replace('\r', '').replace('\n', ' ')
            print(f"    预览: {preview[:100]}...")

    return True
