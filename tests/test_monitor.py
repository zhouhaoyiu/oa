import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from oa_browser import Settings, collect_pages
from oa_core import MonitorError, Store, canonical_link, make_record, single_instance, validate_url


def record(key, title=None, summary=None):
    return make_record("https://oa.example/login", f"/document/{key}", title or key, summary or f"部门\n{title or key}\n2026-10-11点击率 1")


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.store = Store(self.path)

    def baseline(self):
        self.store.ingest("company", [record("A"), record("B")], complete=True)
        self.store.mark_read([row["id"] for row in self.store.notices("company")])

    def test_first_scan_remains_unread(self):
        self.store.ingest("company", [record("A")], complete=True)
        self.assertEqual(len(Store(self.path).notices("company")), 1)

    def test_repeat_scan_does_not_duplicate(self):
        self.baseline()
        self.assertEqual(self.store.ingest("company", [record("A"), record("B")], complete=True), 0)
        self.assertEqual(self.store.notices("company"), [])

    def test_new_below_pinned_head(self):
        self.baseline()
        self.store.ingest("company", [record("A"), record("N"), record("B")], complete=True)
        self.assertEqual([row["title"] for row in self.store.notices("company")], ["N"])

    def test_old_checkpoint_missing(self):
        self.baseline()
        self.store.ingest("company", [record("N"), record("M")], complete=True)
        self.assertEqual(len(self.store.notices("company")), 2)
        self.assertEqual(len(self.store.notices("company", False)), 4)

    def test_duplicate_titles_have_separate_identity(self):
        self.store.ingest("company", [record("A", "通知"), record("B", "通知")], complete=True)
        self.assertEqual(len(self.store.notices("company")), 2)

    def test_updated_record_creates_unread_revision(self):
        self.baseline()
        self.store.ingest("company", [record("A", "修订公告")], complete=True)
        self.assertEqual(self.store.notices("company")[0]["title"], "修订公告")

    def test_click_counts_do_not_create_revision(self):
        self.baseline()
        changed = record("A", summary="部门\nA\n2026-10-11点击率 999")
        self.assertEqual(self.store.ingest("company", [changed], complete=True), 0)

    def test_variable_row_lengths_are_valid(self):
        self.store.ingest("company", [record("A", summary="一行摘要"), record("B", summary="甲\n乙\n丙\n丁")], complete=True)
        self.assertEqual(len(self.store.notices("company")), 2)

    def test_empty_or_incomplete_snapshot_preserves_everything(self):
        self.baseline()
        before = self.path.read_bytes()
        for rows, complete in [([], True), ([record("N")], False)]:
            with self.assertRaises(MonitorError):
                self.store.ingest("company", rows, complete=complete)
            self.assertEqual(self.path.read_bytes(), before)

    def test_conflicting_duplicate_aborts(self):
        with self.assertRaises(MonitorError):
            self.store.ingest("company", [record("A"), record("A", "changed")], complete=True)
        self.assertEqual(self.store.notices("company"), [])

    def test_transaction_rolls_back_partial_insert(self):
        self.baseline()
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER fail_test BEFORE INSERT ON documents WHEN NEW.title='FAIL' BEGIN SELECT RAISE(ABORT,'simulated disk failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.ingest("company", [record("N"), record("X", "FAIL")], complete=True)
        self.assertEqual(self.store.notices("company"), [])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count FROM scans WHERE section='company'").fetchone()[0], 2)

    def test_sections_do_not_consume_each_others_unread(self):
        self.store.ingest("company", [record("A")], complete=True)
        self.store.ingest("notice", [record("A")], complete=True)
        self.store.mark_read([self.store.notices("company")[0]["id"]])
        self.assertEqual(len(self.store.notices("notice")), 1)

    def test_department_filter_does_not_destroy_other_notices(self):
        self.store.ingest("company", [record("A", summary="营销管理部 A"), record("B", summary="基建部 B")], complete=True)
        selected = self.store.notices("company", keywords=("基建部",))
        self.store.mark_read([row["id"] for row in selected])
        self.assertEqual(self.store.notices("company")[0]["title"], "A")

    def test_process_lock_releases_after_error(self):
        lock = Path(self.temp.name) / "monitor.lock"
        with self.assertRaises(ValueError):
            with single_instance(lock):
                with self.assertRaises(MonitorError):
                    with single_instance(lock):
                        pass
                raise ValueError()
        with single_instance(lock):
            pass


class PaginationTests(unittest.TestCase):
    def test_collects_all_pages_with_overlapping_record(self):
        pages = [[record("A"), record("B")], [record("B"), record("N")]]
        index = [0]
        def next_page():
            index[0] += 1
            return index[0] < len(pages)
        self.assertEqual(len(collect_pages(lambda: pages[index[0]], next_page)), 3)

    def test_repeated_page_aborts(self):
        with self.assertRaises(MonitorError):
            collect_pages(lambda: [record("A")], lambda: True)

    def test_limit_aborts_incomplete_scan(self):
        with self.assertRaises(MonitorError):
            collect_pages(lambda: [record("A")], lambda: True, max_pages=1)

    def test_empty_page_aborts(self):
        with self.assertRaises(MonitorError):
            collect_pages(lambda: [], lambda: False)


class ConfigurationTests(unittest.TestCase):
    def test_http_rejected_by_default(self):
        with self.assertRaises(MonitorError):
            validate_url("http://oa.example/login")
        self.assertEqual(validate_url("http://oa.example/login", True), "http://oa.example/login")

    def test_url_embedded_password_rejected(self):
        with self.assertRaises(MonitorError):
            validate_url("https://user:password@oa.example/login")

    def test_credentials_not_enough_without_pagination_configuration(self):
        with patch.dict(os.environ, {"OA_LOGIN_URL": "https://oa.example/login", "OA_USERNAME": "synthetic", "OA_PASSWORD": "synthetic"}, clear=True):
            with self.assertRaises(MonitorError):
                Settings.from_env("company")
            os.environ["OA_NEXT_SELECTOR"] = "#next"
            self.assertEqual(Settings.from_env("company").next_selector, "#next")

    def test_link_identity_canonicalization(self):
        base = "https://oa.example/login"
        self.assertEqual(canonical_link(base, "/doc?id=A&jsessionid=secret#top"), "https://oa.example/doc?id=A")
        for url in ["javascript:open()", "#", "https://other.example/doc/1", "/login", "/doc?access_token=secret"]:
            with self.assertRaises(MonitorError):
                canonical_link(base, url)

    def test_wechat_disabled_without_network(self):
        from wechat import send2wechat
        with self.assertRaises(RuntimeError):
            send2wechat("fake", "fake", "fake", "fake")


if __name__ == "__main__":
    unittest.main()
