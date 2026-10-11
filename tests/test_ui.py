import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from oa_app import show_inbox
from oa_core import Store, make_record


@unittest.skipUnless(os.environ.get("OA_UI_TESTS") == "1", "Set OA_UI_TESTS=1 on a desktop with Tk")
class InboxTests(unittest.TestCase):
    def exercise(self, acknowledge):
        import tkinter as tk
        from tkinter import ttk
        original = tk.Tk
        errors = []
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "test.sqlite3")
            store.ingest("company", [make_record("https://oa.example/", "/doc/1", "合成公告", "测试摘要")], complete=True)
            def create_root():
                root = original()
                root.withdraw()
                def descendants(widget):
                    result = list(widget.winfo_children())
                    return result + [child for item in result for child in descendants(item)]
                def act():
                    try:
                        if acknowledge:
                            widgets = descendants(root)
                            table = next(item for item in widgets if isinstance(item, ttk.Treeview))
                            table.selection_set(table.get_children()[0])
                            next(item for item in widgets if isinstance(item, ttk.Button) and item.cget("text") == "标为已读").invoke()
                    except Exception as exc:
                        errors.append(exc)
                    finally:
                        root.destroy()
                root.after(150, act)
                return root
            with patch("tkinter.Tk", create_root):
                show_inbox(store, "company")
            self.assertEqual(errors, [])
            self.assertEqual(len(store.notices("company")), 0 if acknowledge else 1)

    def test_close_preserves_unread(self):
        self.exercise(False)

    def test_explicit_mark_read_updates_state(self):
        self.exercise(True)
