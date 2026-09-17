"""演示：读取收件箱统计与搜索（写操作默认注释）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 允许直接 `python scripts/example.py` 运行
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from dotenv import load_dotenv

    # parents[3] = 仓库根（scripts → skill → skills → .cursor → repo）
    repo_root = _SCRIPTS_DIR.parents[3]
    env_file = repo_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()
except ImportError:
    pass

from xjtlu_owa_mail import get_authenticated_client


def demo() -> None:
    username = os.environ.get("XJTLU_USERNAME")
    if not username:
        raise SystemExit("请设置环境变量 XJTLU_USERNAME（见 assets/env.example）")

    email_account = f"{username}@student.xjtlu.edu.cn"
    client = get_authenticated_client(email_account)
    if not client:
        raise SystemExit("认证失败：无法获取可用 OWA 会话")

    print("=== 文件夹统计 ===")
    stats = client.folder_stats("inbox")
    if stats:
        print(f"收件箱总数: {stats.total}, 未读: {stats.unread}")
    else:
        print("无法读取收件箱统计")

    print("\n=== 按发件人 + 日期搜索 ===")
    messages = client.find_messages(
        folder="inbox",
        sender="studyabroad",
        since="2026-05-29",
        limit=5,
    )
    if not messages:
        print("未找到符合条件的邮件")
        return

    for i, m in enumerate(messages, 1):
        print(f"[{i}] {m.received} | {m.sender} <{m.sender_email}>")
        print(f"    {m.subject}")
        print(f"    未读={not m.is_read} 附件={m.has_attachments} 预览={m.preview[:80]}")

    first = messages[0]
    print("\n=== 读取第一封正文（Text）===")
    detail = client.get_message(first.item_id, body_type="Text")
    if detail:
        print(detail.body[:600].strip())
        if detail.attachments:
            print(f"\n附件: {[a.name for a in detail.attachments]}")

    print("\n=== 同会话线程 ===")
    thread = client.get_conversation(first.item_id, limit=10)
    print(f"会话邮件数: {len(thread)}")

    # 写操作示例（默认注释，避免误改邮箱）
    # client.mark_read(first.item_id, read=True)
    # client.send_message(to=["target@student.xjtlu.edu.cn"], subject="测试", body="<p>测试</p>")
    # client.reply(first.item_id, "<p>收到，谢谢</p>")
    # client.forward(first.item_id, ["other@student.xjtlu.edu.cn"], "请查收转发")
    # client.move(first.item_id, "deleted")
    # client.delete(first.item_id, hard=False)


if __name__ == "__main__":
    print("=== OWA 邮箱 API 示例 ===")
    demo()
