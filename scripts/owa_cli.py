#!/usr/bin/env python3
"""
XJTLU OWA 邮件命令行（面向 Agent）：所有结果以 JSON 写到 stdout，进度日志写到 stderr。

    owa_cli.py stats [--folder inbox]
    owa_cli.py search [--folder inbox] [--sender X] [--subject Y] [--since 2026-09-01] [--unread] [--limit 20]
    owa_cli.py read ITEM_ID [--html] [--max-chars 20000]
    owa_cli.py thread ITEM_ID
    owa_cli.py attachments ITEM_ID
    owa_cli.py download ITEM_ID [--attachment-id ID] [--out DIR]
    owa_cli.py send --to a@x --subject S (--body TEXT | --body-file F | <stdin>) [--cc] [--bcc] [--attach FILE] [--html|--text] [--draft]
    owa_cli.py reply ITEM_ID (--body TEXT | --body-file F | <stdin>) [--all]
    owa_cli.py forward ITEM_ID --to a@x [--body TEXT]
    owa_cli.py mark-read IDS... [--unread]
    owa_cli.py move IDS... --to FOLDER
    owa_cli.py delete IDS... [--hard]
    owa_cli.py flag IDS... [--clear]
    owa_cli.py categorize IDS... --category C [--category D]
    owa_cli.py login [--force]
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from xjtlu_owa_mail import (  # noqa: E402
    OWAMailClient,
    email_account,
    get_authenticated_client,
    load_project_env,
)


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------


def _to_plain(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        data = {}
        for f in dataclasses.fields(obj):
            if f.name == "raw":
                continue
            data[f.name] = _to_plain(getattr(obj, f.name))
        return data
    if isinstance(obj, (list, tuple)):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    return obj


_REAL_STDOUT = sys.stdout


def emit(payload: Any, *, compact: bool = False) -> None:
    text = json.dumps(_to_plain(payload), ensure_ascii=False, indent=None if compact else 2)
    _REAL_STDOUT.write(text + "\n")
    _REAL_STDOUT.flush()


def fail(message: str, code: int = 1) -> int:
    print(f"[owa-cli] {message}", file=sys.stderr, flush=True)
    emit({"ok": False, "error": message})
    return code


# ---------------------------------------------------------------------------
# 参数辅助
# ---------------------------------------------------------------------------


def _split_addresses(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for v in values or []:
        for part in v.replace(";", ",").split(","):
            part = part.strip()
            if part:
                out.append(part)
    return out


def _read_body(args: argparse.Namespace, *, required: bool = True) -> str:
    if getattr(args, "body", None) is not None:
        return args.body
    if getattr(args, "body_file", None):
        return Path(args.body_file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip() or not required:
            return data
    if required:
        raise SystemExit("缺少正文：请用 --body、--body-file 或通过 stdin 传入")
    return ""


def _body_type(args: argparse.Namespace) -> str:
    if getattr(args, "html", False):
        return "HTML"
    if getattr(args, "text", False):
        return "Text"
    return "auto"


def _add_body_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--body", help="正文文本；含 HTML 标签则按 HTML 发送，否则按纯文本发送（保留换行）")
    p.add_argument("--body-file", help="从文件读取正文（UTF-8）")
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("--html", action="store_true", help="强制按 HTML 发送（纯文本会自动转成 <p>/<br>）")
    fmt.add_argument("--text", action="store_true", help="强制按纯文本发送")


def _client(args: argparse.Namespace) -> OWAMailClient:
    load_project_env()
    account = args.account or email_account()
    client = get_authenticated_client(account, force_refresh=getattr(args, "force", False))
    if not client:
        raise SystemExit("认证失败：无法获取可用 OWA 会话（检查 .env 凭据 / 网络）")
    return client


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------


def cmd_login(args: argparse.Namespace) -> Any:
    load_project_env()
    account = args.account or email_account()
    client = _client(args)
    stats = client.folder_stats("inbox")
    return {"ok": True, "account": account, "inbox": stats}


def cmd_stats(args: argparse.Namespace) -> Any:
    client = _client(args)
    stats = client.folder_stats(args.folder)
    if stats is None:
        raise SystemExit(f"无法读取文件夹统计: {args.folder}")
    return {"ok": True, **_to_plain(stats)}


def cmd_search(args: argparse.Namespace) -> Any:
    client = _client(args)
    has_att: bool | None = None
    if args.has_attachments:
        has_att = True
    elif args.no_attachments:
        has_att = False
    messages = client.find_messages(
        args.folder,
        sender=args.sender,
        recipient=args.recipient,
        subject=args.subject,
        body=args.body,
        since=args.since,
        until=args.until,
        unread_only=args.unread,
        read_only=args.read,
        has_attachments=has_att,
        importance=args.importance,
        sort_by=args.sort,
        ascending=args.asc,
        limit=args.limit,
        offset=args.offset,
    )
    return {"ok": True, "folder": args.folder, "count": len(messages), "messages": messages}


def cmd_read(args: argparse.Namespace) -> Any:
    client = _client(args)
    detail = client.get_message(args.item_id, body_type="HTML" if args.html else "Text")
    if detail is None:
        raise SystemExit("邮件不存在或无法读取（ItemId 可能已失效）")
    body = detail.body or ""
    truncated = False
    if args.max_chars and len(body) > args.max_chars:
        body = body[: args.max_chars]
        truncated = True
    data = _to_plain(detail)
    data["body"] = body
    data["truncated"] = truncated
    return {"ok": True, **data}


def cmd_thread(args: argparse.Namespace) -> Any:
    client = _client(args)
    messages = client.get_conversation(args.item_id, limit=args.limit)
    return {"ok": True, "count": len(messages), "messages": messages}


def cmd_attachments(args: argparse.Namespace) -> Any:
    client = _client(args)
    atts = client.list_attachments(args.item_id)
    return {"ok": True, "count": len(atts), "attachments": atts}


def cmd_download(args: argparse.Namespace) -> Any:
    client = _client(args)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.attachment_id:
        targets = [(args.attachment_id, None)]
    else:
        atts = client.list_attachments(args.item_id)
        targets = [(a.attachment_id, a.name) for a in atts if not a.is_inline or args.include_inline]
    saved: list[str] = []
    for att_id, _name in targets:
        path = client.download_attachment(att_id, out_dir)
        if path:
            saved.append(str(path))
    return {"ok": bool(saved) or not targets, "saved": saved, "requested": len(targets)}


def _attachments_from_args(paths: list[str] | None) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for p in paths or []:
        fp = Path(p)
        if not fp.is_file():
            raise SystemExit(f"附件不存在: {p}")
        out.append((fp.name, fp.read_bytes()))
    return out


def cmd_send(args: argparse.Namespace) -> Any:
    to = _split_addresses(args.to)
    if not to:
        raise SystemExit("至少需要一个收件人 --to")
    body = _read_body(args)
    client = _client(args)
    ok = client.send_message(
        to,
        args.subject,
        body,
        cc=_split_addresses(args.cc) or None,
        bcc=_split_addresses(args.bcc) or None,
        body_type=_body_type(args),
        attachments=_attachments_from_args(args.attach) or None,
        draft=args.draft,
    )
    if not ok:
        raise SystemExit("发送失败: " + "; ".join(client.last_errors))
    return {"ok": True, "action": "draft" if args.draft else "sent", "to": to, "subject": args.subject}


def cmd_reply(args: argparse.Namespace) -> Any:
    body = _read_body(args)
    client = _client(args)
    ok = client.reply(args.item_id, body, reply_all=args.all, body_type=_body_type(args))
    if not ok:
        raise SystemExit("回复失败: " + "; ".join(client.last_errors))
    return {"ok": True, "action": "reply_all" if args.all else "reply", "item_id": args.item_id}


def cmd_forward(args: argparse.Namespace) -> Any:
    to = _split_addresses(args.to)
    if not to:
        raise SystemExit("至少需要一个收件人 --to")
    body = _read_body(args, required=False)
    client = _client(args)
    ok = client.forward(args.item_id, to, body, body_type=_body_type(args))
    if not ok:
        raise SystemExit("转发失败: " + "; ".join(client.last_errors))
    return {"ok": True, "action": "forward", "item_id": args.item_id, "to": to}


def cmd_mark_read(args: argparse.Namespace) -> Any:
    client = _client(args)
    ok = client.mark_read(args.item_ids, read=not args.unread)
    return {"ok": ok, "action": "mark_unread" if args.unread else "mark_read", "count": len(args.item_ids), "errors": client.last_errors}


def cmd_move(args: argparse.Namespace) -> Any:
    client = _client(args)
    ok = client.move(args.item_ids, args.to)
    return {"ok": ok, "action": "move", "to": args.to, "count": len(args.item_ids), "errors": client.last_errors}


def cmd_delete(args: argparse.Namespace) -> Any:
    client = _client(args)
    ok = client.delete(args.item_ids, hard=args.hard)
    return {"ok": ok, "action": "hard_delete" if args.hard else "move_to_deleted", "count": len(args.item_ids), "errors": client.last_errors}


def cmd_flag(args: argparse.Namespace) -> Any:
    client = _client(args)
    ok = client.set_flag(args.item_ids, flagged=not args.clear)
    return {"ok": ok, "action": "unflag" if args.clear else "flag", "count": len(args.item_ids), "errors": client.last_errors}


def cmd_categorize(args: argparse.Namespace) -> Any:
    client = _client(args)
    ok = client.categorize(args.item_ids, args.category)
    return {"ok": ok, "action": "categorize", "categories": args.category, "count": len(args.item_ids), "errors": client.last_errors}


# ---------------------------------------------------------------------------
# 解析器
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="owa",
        description="XJTLU OWA 邮件命令行：结果 JSON 输出到 stdout，日志输出到 stderr。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--account", help="完整邮箱地址；默认 XJTLU_EMAIL 或 XJTLU_USERNAME@student.xjtlu.edu.cn")
    parser.add_argument("--compact", action="store_true", help="单行 JSON 输出")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("login", help="验证/刷新登录并返回收件箱统计")
    p.add_argument("--force", action="store_true", help="跳过缓存，强制走 UIM 完整登录")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("stats", help="文件夹总数与未读数")
    p.add_argument("--folder", default="inbox")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("search", help="按条件搜索邮件（服务端过滤）")
    p.add_argument("--folder", default="inbox", help="inbox/sent/drafts/deleted/junk/archive 或自定义文件夹名")
    p.add_argument("--sender", help="发件人名称或地址子串")
    p.add_argument("--recipient", help="收件人子串")
    p.add_argument("--subject", help="主题子串")
    p.add_argument("--body", help="正文子串")
    p.add_argument("--since", help="起始日期（含），如 2026-09-01 或 ISO 时间")
    p.add_argument("--until", help="截止日期（不含）")
    p.add_argument("--unread", action="store_true", help="只看未读")
    p.add_argument("--read", action="store_true", help="只看已读")
    p.add_argument("--has-attachments", action="store_true")
    p.add_argument("--no-attachments", action="store_true")
    p.add_argument("--importance", choices=["Low", "Normal", "High"])
    p.add_argument("--sort", default="received", choices=["received", "date", "sent", "subject", "from", "size"])
    p.add_argument("--asc", action="store_true", help="升序（默认降序，最新在前）")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("read", help="读取单封邮件正文与元数据")
    p.add_argument("item_id")
    p.add_argument("--html", action="store_true", help="返回 HTML 正文（默认纯文本）")
    p.add_argument("--max-chars", type=int, default=20000, help="正文最大字符数，0 为不截断")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("thread", help="同会话线程中的邮件")
    p.add_argument("item_id")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_thread)

    p = sub.add_parser("attachments", help="列出附件元数据")
    p.add_argument("item_id")
    p.set_defaults(func=cmd_attachments)

    p = sub.add_parser("download", help="下载附件到目录")
    p.add_argument("item_id")
    p.add_argument("--attachment-id", help="只下载指定附件；缺省下载该邮件全部非内嵌附件")
    p.add_argument("--out", default="./downloads", help="保存目录")
    p.add_argument("--include-inline", action="store_true", help="同时下载内嵌图片")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("send", help="发送新邮件（或存草稿）")
    p.add_argument("--to", action="append", required=True, help="收件人，可重复或逗号分隔")
    p.add_argument("--cc", action="append")
    p.add_argument("--bcc", action="append")
    p.add_argument("--subject", required=True)
    _add_body_flags(p)
    p.add_argument("--attach", action="append", help="附件文件路径，可重复")
    p.add_argument("--draft", action="store_true", help="只保存到草稿箱，不发送")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("reply", help="回复邮件")
    p.add_argument("item_id")
    _add_body_flags(p)
    p.add_argument("--all", action="store_true", help="回复全部")
    p.set_defaults(func=cmd_reply)

    p = sub.add_parser("forward", help="转发邮件")
    p.add_argument("item_id")
    p.add_argument("--to", action="append", required=True)
    _add_body_flags(p)
    p.set_defaults(func=cmd_forward)

    p = sub.add_parser("mark-read", help="标记已读/未读")
    p.add_argument("item_ids", nargs="+")
    p.add_argument("--unread", action="store_true", help="标记为未读")
    p.set_defaults(func=cmd_mark_read)

    p = sub.add_parser("move", help="移动到文件夹")
    p.add_argument("item_ids", nargs="+")
    p.add_argument("--to", required=True, help="目标文件夹（别名或显示名）")
    p.set_defaults(func=cmd_move)

    p = sub.add_parser("delete", help="删除（默认移到已删除邮件）")
    p.add_argument("item_ids", nargs="+")
    p.add_argument("--hard", action="store_true", help="永久删除，不可恢复")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("flag", help="设置/清除旗标")
    p.add_argument("item_ids", nargs="+")
    p.add_argument("--clear", action="store_true")
    p.set_defaults(func=cmd_flag)

    p = sub.add_parser("categorize", help="设置类别")
    p.add_argument("item_ids", nargs="+")
    p.add_argument("--category", action="append", required=True)
    p.set_defaults(func=cmd_categorize)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # 依赖库（登录包等）里的 print 全部转到 stderr，保证 stdout 只有最终 JSON。
    with contextlib.redirect_stdout(sys.stderr):
        try:
            result = args.func(args)
        except SystemExit as exc:
            if isinstance(exc.code, str):
                return fail(exc.code)
            raise
        except Exception as exc:  # noqa: BLE001
            return fail(f"{type(exc).__name__}: {exc}")
    emit(result, compact=args.compact)
    return 0


if __name__ == "__main__":
    sys.exit(main())
