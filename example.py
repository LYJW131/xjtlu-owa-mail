"""Python 库用法示例：python3 example.py"""

from xjtlu_owa_mail import email_account, get_authenticated_client


def demo() -> None:
    client = get_authenticated_client(email_account())
    if not client:
        raise SystemExit("认证失败：无法获取可用 OWA 会话")

    print("=== 文件夹统计 ===")
    stats = client.folder_stats("inbox")
    if stats:
        print(f"收件箱总数: {stats.total}, 未读: {stats.unread}")

    print("\n=== 最近 5 封 ===")
    messages = client.find_messages("inbox", limit=5)
    for i, m in enumerate(messages, 1):
        print(f"[{i}] {m.received} | {m.sender} <{m.sender_email}>")
        print(f"    {m.subject}")
        print(f"    未读={not m.is_read} 附件={m.has_attachments} 预览={m.preview[:80]}")
    if not messages:
        return

    first = messages[0]
    print("\n=== 读取第一封正文（Text）===")
    detail = client.get_message(first.item_id, body_type="Text")
    if detail:
        print(detail.body[:600].strip())
        if detail.attachments:
            print(f"\n附件: {[a.name for a in detail.attachments]}")

    # -------------------------------------------------------
    # 写操作示例（默认注释，避免误改邮箱）
    # -------------------------------------------------------
    # client.send_message(
    #     to=["target@student.xjtlu.edu.cn"],
    #     subject="测试邮件",
    #     body="第一行\n第二行",           # 纯文本自动保留换行；含 HTML 标签则按 HTML 发送
    # )
    # client.reply(first.item_id, "收到，谢谢")
    # client.forward(first.item_id, ["other@student.xjtlu.edu.cn"], "请查收转发")
    # client.mark_read(first.item_id, read=True)
    # client.delete(first.item_id, hard=False)


if __name__ == "__main__":
    demo()
