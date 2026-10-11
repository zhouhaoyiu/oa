"""One-shot collection plus a persistent local unread inbox. No WeChat integration."""

import argparse
import logging
import os
from pathlib import Path
import sys
import webbrowser
from oa_browser import Settings, fetch_records
from oa_core import MonitorError, Store, single_instance


DEPARTMENTS = ("企业发展策划部", "调度运行部", "生产技术部", "基建部", "安全保卫部")


def state_directory():
    if os.environ.get("OA_STATE_DIR"):
        return Path(os.environ["OA_STATE_DIR"]).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OAReader"
    return Path.home() / ".local" / "share" / "oa-reader"


def show_inbox(store, section, keywords=(), error=""):
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("OA 本地提醒 · " + ("通知公告" if section == "notice" else "公司文件"))
    root.geometry("900x620")
    root.minsize(640, 420)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)
    toolbar = ttk.Frame(root, padding=12)
    toolbar.grid(row=0, column=0, sticky="ew")
    unread = tk.BooleanVar(value=True)
    status = tk.StringVar()
    frame = ttk.Frame(root)
    frame.grid(row=1, column=0, sticky="nsew", padx=12)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    table = ttk.Treeview(frame, columns=("state", "title", "time"), show="headings", selectmode="extended")
    for name, title, width in [("state", "状态", 60), ("title", "公告", 540), ("time", "收录时间 UTC", 150)]:
        table.heading(name, text=title)
        table.column(name, width=width, minwidth=50, stretch=name == "title")
    table.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    table.configure(yscrollcommand=scroll.set)
    details = tk.Text(root, height=7, wrap="word", state="disabled")
    details.grid(row=2, column=0, sticky="ew", padx=12, pady=12)
    current = {}

    def refresh():
        current.clear()
        table.delete(*table.get_children())
        rows = store.notices(section, unread.get(), keywords)
        for row in rows:
            current[str(row["id"])] = row
            table.insert("", "end", iid=str(row["id"]), values=("已读" if row["is_read"] else "未读", row["title"], row["created_at"]))
        pending = len(store.notices(section, True, keywords))
        status.set(f"未读 {pending} · 当前 {len(rows)} 条" + (f" · {error}" if error else ""))

    def select(_event=None):
        selected = table.selection()
        details.configure(state="normal")
        details.delete("1.0", "end")
        if selected:
            details.insert("1.0", current[selected[0]]["summary"])
        details.configure(state="disabled")

    def mark_read():
        store.mark_read([int(item) for item in table.selection()])
        refresh()
        select()

    def open_record():
        selected = table.selection()
        if selected:
            webbrowser.open(current[selected[0]]["url"])

    ttk.Checkbutton(toolbar, text="仅未读", variable=unread, command=refresh).pack(side="left")
    ttk.Button(toolbar, text="标为已读", command=mark_read).pack(side="left", padx=12)
    ttk.Button(toolbar, text="打开原文", command=open_record).pack(side="left")
    ttk.Label(root, textvariable=status, padding=12, wraplength=850).grid(row=3, column=0, sticky="ew")
    table.bind("<<TreeviewSelect>>", select)
    table.bind("<Double-1>", lambda event: open_record())
    refresh()
    if error:
        root.after(100, lambda: messagebox.showwarning("本次抓取未完成", error, parent=root))
    root.mainloop()


def run(default_section="company", default_departments=False):
    parser = argparse.ArgumentParser(description="OA 本地未读提醒，不发送微信消息。")
    parser.add_argument("--section", choices=["company", "notice"], default=default_section)
    parser.add_argument("--history", action="store_true", help="只查看本地记录，不联网")
    parser.add_argument("--no-ui", action="store_true", help="抓取后保留未读，不弹窗也不标记已读")
    args = parser.parse_args()
    directory = state_directory()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    logging.basicConfig(filename=directory / "monitor.log", encoding="utf-8", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        with single_instance(directory / "monitor.lock"):
            store = Store(directory / "monitor.sqlite3")
            error = ""
            if not args.history:
                try:
                    settings = Settings.from_env(args.section)
                    records = fetch_records(settings)
                    added = store.ingest(args.section, records, complete=True)
                    logging.info("section=%s collected=%d new_revisions=%d", args.section, len(records), added)
                except Exception as exc:
                    # Browser exception strings can contain URLs or entered values.
                    error = str(exc) if isinstance(exc, MonitorError) else f"抓取失败（{type(exc).__name__}），旧进度和未读记录已保留。"
                    logging.error("%s", error)
            if args.no_ui:
                print(error or f"未读 {len(store.notices(args.section))} 条，未发送任何外部通知。")
            else:
                show_inbox(store, args.section, DEPARTMENTS if default_departments else (), error)
            return 1 if error else 0
    except MonitorError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
