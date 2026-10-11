"""Local state and validation. This module never accesses OA or messaging APIs."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


class MonitorError(Exception):
    pass


def validate_url(value, allow_http=False):
    parsed = urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password:
        raise MonitorError("OA_LOGIN_URL 必须是有效地址，不能在地址中包含账号密码。")
    if parsed.scheme != "https" and not (allow_http and parsed.scheme == "http"):
        raise MonitorError("默认只允许 HTTPS；确认内网风险后才能设置 OA_ALLOW_INSECURE_HTTP=1。")
    return value


def canonical_link(base, href):
    if not href or href.strip().startswith(("#", "javascript:", "mailto:")):
        raise MonitorError("公告缺少可追溯的详情链接，请配置公告链接选择器。")
    target, origin = urlsplit(urljoin(base, href)), urlsplit(base)
    if (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
        raise MonitorError("公告链接指向另一站点，已停止本次抓取。")
    if target.path in ("", "/") or "login" in target.path.lower():
        raise MonitorError("公告链接不是详情地址。")
    query = [(key, val) for key, val in parse_qsl(target.query, keep_blank_values=True)
             if key.lower() not in {"jsessionid", "sessionid"}]
    if any(key.lower() in {"token", "access_token", "password"} for key, _ in query):
        raise MonitorError("详情地址含敏感参数，不能作为公告标识。")
    path = target.path.split(";jsessionid=", 1)[0]
    return urlunsplit((target.scheme, target.netloc, path, urlencode(sorted(query)), ""))


@dataclass(frozen=True)
class Record:
    key: str
    title: str
    summary: str
    url: str

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps([self.title, self.summary, self.url],
                             ensure_ascii=False).encode("utf-8")).hexdigest()


def make_record(base, href, title, text):
    url = canonical_link(base, href)
    summary = "\n".join(line.strip() for line in text.split("点击率", 1)[0].splitlines() if line.strip())
    if not title.strip() or not summary:
        raise MonitorError("公告标题或摘要为空，本次进度未更新。")
    return Record(hashlib.sha256(url.encode()).hexdigest(), title.strip(), summary, url)


def validate_snapshot(records, complete):
    if not complete or not records:
        raise MonitorError("未取得完整、非空的公告列表，保留原有进度。")
    unique = {}
    for item in records:
        if not isinstance(item, Record) or not all((item.key, item.title, item.summary, item.url)):
            raise MonitorError("公告数据不完整，保留原有进度。")
        if item.key in unique and unique[item.key] != item:
            raise MonitorError("同一公告出现冲突内容，可能在翻页期间更新；请重新抓取。")
        unique[item.key] = item
    return list(unique.values())


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    section TEXT NOT NULL, key TEXT NOT NULL, title TEXT NOT NULL,
                    summary TEXT NOT NULL, url TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    PRIMARY KEY(section, key));
                CREATE TABLE IF NOT EXISTS notices (
                    id INTEGER PRIMARY KEY, section TEXT NOT NULL, key TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL,
                    url TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS scans (
                    section TEXT PRIMARY KEY, last_success TEXT NOT NULL, count INTEGER NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def ingest(self, section, records, *, complete):
        records = validate_snapshot(records, complete)
        added = 0
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for item in records:
                previous = db.execute("SELECT fingerprint FROM documents WHERE section=? AND key=?",
                                      (section, item.key)).fetchone()
                if previous is None or previous[0] != item.fingerprint:
                    db.execute("INSERT INTO notices(section,key,fingerprint,title,summary,url) VALUES(?,?,?,?,?,?)",
                               (section, item.key, item.fingerprint, item.title, item.summary, item.url))
                    added += 1
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?) ON CONFLICT(section,key) DO UPDATE SET "
                           "title=excluded.title,summary=excluded.summary,url=excluded.url,fingerprint=excluded.fingerprint",
                           (section, item.key, item.title, item.summary, item.url, item.fingerprint))
            db.execute("INSERT INTO scans VALUES(?,CURRENT_TIMESTAMP,?) ON CONFLICT(section) DO UPDATE SET "
                       "last_success=excluded.last_success,count=excluded.count", (section, len(records)))
        return added

    def notices(self, section, unread_only=True, keywords=()):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM notices WHERE section=? " +
                              ("AND is_read=0 " if unread_only else "") + "ORDER BY id DESC", (section,)).fetchall()
        return [dict(row) for row in rows if not keywords or any(word in row["summary"] for word in keywords)]

    def mark_read(self, ids):
        with self.connect() as db:
            db.executemany("UPDATE notices SET is_read=1 WHERE id=?", [(item,) for item in ids])


@contextmanager
def single_instance(path):
    """Use OS locks; release on process exit without a stale PID-file protocol."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    acquired = False
    try:
        if path.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise MonitorError("已有一个 OA 提醒实例在运行。") from exc
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()
