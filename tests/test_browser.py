"""Opt-in real Chrome checks against a synthetic localhost OA, never the real OA."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from threading import Thread
import unittest
from urllib.parse import parse_qs, urlsplit

from oa_browser import Settings, fetch_records
from oa_core import MonitorError


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/list"):
            second = parse_qs(urlsplit(self.path).query).get("page") == ["2"]
            ids = ["A", "N"] if not second else ["M", "B"]
            rows = "".join(f'<div class="lui_listview_rowtable_summary_content_box"><a href="/doc/{key}">同名公告 {key}</a><p>合成测试部门</p></div>' for key in ids)
            page = rows + ('<button id="next" disabled>下一页</button>' if second else '<button id="next" onclick="setTimeout(()=>location.href=\'/list?page=2\',300)">下一页</button>')
        elif self.path == "/broken":
            page = "<p>合成登录失败页面</p>"
        else:
            page = '''<input class="lui_login_input_username"><input class="lui_login_input_password" type="password">
              <button class="lui_login_button_div_c" onclick="setTimeout(login,300)">登录</button>
              <script>
                function login() { document.body.innerHTML = '<button class="lui_portal_header_menu_item_c">首页</button><button class="lui_portal_header_menu_item_c" onclick="more()">信息门户</button>'; }
                function more() { setTimeout(()=>{
                  document.body.replaceChildren();
                  for(let n=0;n<3;n++) { const button=document.createElement('button');
                    button.className='lui_portlet_operation_more'; button.textContent='更多';
                    button.onclick=()=>window.open('/list?page=1'); document.body.append(button); }
                },300); }
              </script>'''
        content = ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><body>" + page + "</body></html>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


@unittest.skipUnless(os.environ.get("OA_BROWSER_TESTS") == "1", "Set OA_BROWSER_TESTS=1 for local Chrome integration")
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def factory(self, options):
        from selenium import webdriver
        self.driver = webdriver.Chrome(options=options)
        self.quit_called = False
        original = self.driver.quit
        def quit_driver():
            self.quit_called = True
            original()
        self.driver.quit = quit_driver
        return self.driver

    def test_delayed_login_new_window_and_pagination(self):
        settings = Settings(self.base + "/login", "fake", "fake", "company", next_selector="#next", timeout=5)
        records = fetch_records(settings, self.factory)
        self.assertEqual(len(records), 4)
        self.assertTrue(self.quit_called)

    def test_failed_login_still_closes_browser(self):
        settings = Settings(self.base + "/broken", "fake", "fake", "notice", next_selector="#next", timeout=1)
        with self.assertRaises(MonitorError):
            fetch_records(settings, self.factory)
        self.assertTrue(self.quit_called)


if __name__ == "__main__":
    unittest.main()
