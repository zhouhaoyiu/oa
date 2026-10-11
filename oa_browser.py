"""Selenium adapter for the existing OA page; selectors remain configurable."""

from dataclasses import dataclass
import os
from oa_core import MonitorError, make_record, validate_snapshot, validate_url


@dataclass(frozen=True)
class Settings:
    url: str
    username: str
    password: str
    section: str
    next_selector: str = ""
    single_page: bool = False
    row_selector: str = ".lui_listview_rowtable_summary_content_box"
    link_selector: str = "a[href]"
    timeout: float = 30
    max_pages: int = 100

    @classmethod
    def from_env(cls, section):
        url = validate_url(os.environ.get("OA_LOGIN_URL", ""), os.environ.get("OA_ALLOW_INSECURE_HTTP") == "1")
        username, password = os.environ.get("OA_USERNAME", ""), os.environ.get("OA_PASSWORD", "")
        if not username or not password:
            raise MonitorError("请在本机设置 OA_USERNAME 和 OA_PASSWORD，不要发送给他人。")
        next_selector = os.environ.get("OA_NEXT_SELECTOR", "")
        single_page = os.environ.get("OA_SINGLE_PAGE") == "1"
        if not next_selector and not single_page:
            raise MonitorError("需设置 OA_NEXT_SELECTOR；确认该列表无分页时才可设置 OA_SINGLE_PAGE=1。")
        return cls(url, username, password, section, next_selector, single_page,
                   os.environ.get("OA_ROW_SELECTOR", cls.row_selector),
                   os.environ.get("OA_LINK_SELECTOR", cls.link_selector))


def collect_pages(read_page, next_page, max_pages=100):
    result, seen_pages = [], set()
    for _ in range(max_pages):
        records = validate_snapshot(read_page(), complete=True)
        signature = tuple((row.key, row.fingerprint) for row in records)
        if signature in seen_pages:
            raise MonitorError("分页重复或未前进，保留原有进度。")
        seen_pages.add(signature)
        result.extend(records)
        if not next_page():
            return validate_snapshot(result, complete=True)
    raise MonitorError("达到分页上限，未保存不完整的抓取结果。")


def fetch_records(settings, driver_factory=None):
    from selenium import webdriver
    from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = None
    try:
        driver = (driver_factory or (lambda opts: webdriver.Chrome(options=opts)))(options)
        driver.set_page_load_timeout(settings.timeout)
        wait = WebDriverWait(driver, settings.timeout, poll_frequency=0.2,
                             ignored_exceptions=(StaleElementReferenceException,))
        driver.get(settings.url)
        # Refuse an HTTPS-to-HTTP login redirect before entering any credentials.
        validate_url(driver.current_url, settings.url.startswith("http://"))
        from urllib.parse import urlsplit
        if urlsplit(driver.current_url).netloc != urlsplit(settings.url).netloc:
            raise MonitorError("登录页跳转到了另一站点，未填写凭据。")
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "lui_login_input_username"))).send_keys(settings.username)
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "lui_login_input_password"))).send_keys(settings.password)
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "lui_login_button_div_c"))).click()

        def indexed_clickable(class_name, index):
            def locate(browser):
                elements = browser.find_elements(By.CLASS_NAME, class_name)
                if len(elements) > index and elements[index].is_displayed() and elements[index].is_enabled():
                    return elements[index]
                return False
            return wait.until(locate)

        indexed_clickable("lui_portal_header_menu_item_c", 1).click()
        more = indexed_clickable("lui_portlet_operation_more", 2 if settings.section == "notice" else 0)
        handles = set(driver.window_handles)
        more.click()

        def list_window(browser):
            new = set(browser.window_handles) - handles
            if len(new) > 1:
                raise MonitorError("出现多个新窗口，不能确定公告列表。")
            if new:
                browser.switch_to.window(next(iter(new)))
            return browser.find_elements(By.CSS_SELECTOR, settings.row_selector)

        wait.until(list_window)

        def read_page():
            def extract(browser):
                elements = browser.find_elements(By.CSS_SELECTOR, settings.row_selector)
                if not elements:
                    return False
                records = []
                for element in elements:
                    links = element.find_elements(By.CSS_SELECTOR, settings.link_selector)
                    if not links:
                        containers = element.find_elements(By.XPATH, "./ancestor::tr[1]")
                        if containers:
                            links = containers[0].find_elements(By.CSS_SELECTOR, settings.link_selector)
                    candidates = {}
                    for link in links:
                        href = link.get_attribute("href")
                        title = link.text.strip() or (link.get_attribute("title") or "").strip()
                        if href and title:
                            candidates[href] = title
                    if not candidates:
                        return False
                    if len(candidates) != 1:
                        raise MonitorError("无法唯一识别公告详情链接；请核对 OA_LINK_SELECTOR，未更新进度。")
                    href, title = next(iter(candidates.items()))
                    records.append(make_record(settings.url, href, title, element.text))
                return records
            return wait.until(extract)

        def next_page():
            if settings.single_page:
                return False
            elements = driver.find_elements(By.CSS_SELECTOR, settings.next_selector)
            if len(elements) != 1:
                raise MonitorError("未唯一找到下一页控件，不能确认抓取完整性。")
            button = elements[0]
            disabled = (not button.is_enabled() or button.get_attribute("aria-disabled") == "true"
                        or "disabled" in (button.get_attribute("class") or "").lower())
            if disabled:
                return False
            before = [(item.key, item.fingerprint) for item in read_page()]
            button.click()
            wait.until(lambda _: [(item.key, item.fingerprint) for item in read_page()] != before)
            return True

        return collect_pages(read_page, next_page, settings.max_pages)
    except TimeoutException as exc:
        raise MonitorError("登录、列表或翻页等待超时；进度未更新，请检查网络及页面结构。") from exc
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
