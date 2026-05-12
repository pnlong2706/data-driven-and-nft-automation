"""Non-functional tests for Search Course: performance, XSS resilience, SQL injection, long input.

NOTE: These tests do NOT use the sort/display dropdowns, so they don't need the
Bootstrap dropdown workaround.  They only type into the search field.
"""
import re
import time
import unittest

from selenium import webdriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ── Hard-coded constants ──────────────────────────────────────────────
LOGIN_URL = "https://school.moodledemo.net/login/index.php"
COURSES_URL = "https://school.moodledemo.net/my/courses.php"
SUCCESS_FRAGMENT = "/my/"

USERNAME_ID = "username"
PASSWORD_ID = "password"
LOGIN_BTN_ID = "loginbtn"

SEARCH_INPUT_NAME = "search"
SORT_DROPDOWN_ID = "sortingdropdown"
DISPLAY_DROPDOWN_ID = "displaydropdown"
COURSE_INFO_CSS = ".course-info-container"
NO_COURSES_TEXT = "No courses"

CREDENTIALS = ("student", "moodle26")

PERF_BUDGET = 15.0

LEAK_REGEX = re.compile(
    "|".join([
        r"Stack\s+trace:\s*\n",
        r"debug_info\s*[:=]",
        r"SQLSTATE\[",
        r"dml_(read|write)_exception",
        r"coding_exception",
        r"\bmysqli_\w+",
        r"Fatal\s+error:\s",
        r"Warning:\s+\w+\(\)",
        r"Notice:\s+Undefined",
        r"\.php\s+on\s+line\s+\d+",
        r"Uncaught\s+\w*Exception",
    ])
)

XSS_PAYLOADS = [
    '<script>alert("xss")</script>',
    '"><img src=x onerror=alert(1)>',
    "'\"><svg/onload=alert(1)>",
]
SQL_INJECTION_PAYLOADS = [
    "' OR 1=1 --",
    "'; DROP TABLE mdl_course; --",
    '" UNION SELECT * FROM mdl_user --',
]


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.page_load_strategy = "eager"
    return webdriver.Chrome(options=opts)


class TestSearchCourseNonFunctional(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.driver.set_page_load_timeout(60)
        cls.wait = WebDriverWait(cls.driver, 30)
        cls._login()

    @classmethod
    def _login(cls):
        d = cls.driver
        try:
            d.get(LOGIN_URL)
        except TimeoutException:
            pass
        d.delete_all_cookies()
        try:
            d.get(LOGIN_URL)
        except TimeoutException:
            pass
        WebDriverWait(d, 30).until(
            EC.presence_of_element_located((By.ID, USERNAME_ID))
        )
        d.find_element(By.ID, USERNAME_ID).send_keys(CREDENTIALS[0])
        d.find_element(By.ID, PASSWORD_ID).send_keys(CREDENTIALS[1])
        d.find_element(By.ID, LOGIN_BTN_ID).click()
        try:
            WebDriverWait(d, 30).until(
                lambda dr: SUCCESS_FRAGMENT in dr.current_url
            )
        except TimeoutException:
            raise RuntimeError("Login failed – cannot proceed with search tests")

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    # ── Helpers ─────────────────────────────────────────────────────────

    def open_courses_page(self):
        try:
            self.driver.get(COURSES_URL)
        except TimeoutException:
            pass
        try:
            self.wait.until(
                EC.presence_of_element_located((By.NAME, SEARCH_INPUT_NAME))
            )
        except TimeoutException:
            # Session likely expired — re-login
            self._login()
            try:
                self.driver.get(COURSES_URL)
            except TimeoutException:
                pass
            self.wait.until(
                EC.presence_of_element_located((By.NAME, SEARCH_INPUT_NAME))
            )
        # Wait for Moodle JS to bind
        time.sleep(5)

    def _type_into(self, field_name, text):
        for _ in range(4):
            try:
                el = self.driver.find_element(By.NAME, field_name)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el
                )
                el.clear()
                if text:
                    el.send_keys(text)
                return
            except (StaleElementReferenceException, ElementNotInteractableException):
                time.sleep(0.4)
        el = self.driver.find_element(By.NAME, field_name)
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el, text or "",
        )

    def _wait_for_search_results(self, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            has_cards = len(self.driver.find_elements(By.CSS_SELECTOR, COURSE_INFO_CSS)) > 0
            has_no_courses = NO_COURSES_TEXT in self.driver.find_element(By.TAG_NAME, "body").text
            if has_cards or has_no_courses:
                return
            time.sleep(0.5)

    # ── Performance test ────────────────────────────────────────────────

    def test_performance_search_response_time(self):
        """Valid search should return results within PERF_BUDGET seconds."""
        self.open_courses_page()
        self._type_into(SEARCH_INPUT_NAME, "Moodle Mountain")

        start = time.time()
        self._wait_for_search_results(timeout=20)
        elapsed = time.time() - start

        self.assertLessEqual(
            elapsed, PERF_BUDGET,
            f"Search took {elapsed:.2f}s, budget is {PERF_BUDGET}s",
        )

    # ── Security: XSS ──────────────────────────────────────────────────

    def test_security_xss_not_reflected(self):
        """XSS payloads must not be reflected as executable HTML in the page."""
        for payload in XSS_PAYLOADS:
            with self.subTest(payload=payload):
                self.open_courses_page()
                self._type_into(SEARCH_INPUT_NAME, payload)
                self._wait_for_search_results(timeout=15)

                page_source = self.driver.page_source or ""
                self.assertNotIn(
                    "<script>", page_source,
                    f"XSS payload reflected as <script> in page: {payload!r}",
                )
                leak = LEAK_REGEX.search(page_source)
                self.assertIsNone(
                    leak,
                    f"Page leaked debug info after XSS input: {leak.group(0) if leak else ''}",
                )

    # ── Security: SQL Injection ────────────────────────────────────────

    def test_security_sql_injection_no_leak(self):
        """SQL injection payloads must not cause DB errors to leak."""
        for payload in SQL_INJECTION_PAYLOADS:
            with self.subTest(payload=payload):
                self.open_courses_page()
                self._type_into(SEARCH_INPUT_NAME, payload)
                self._wait_for_search_results(timeout=15)

                page_source = self.driver.page_source or ""
                leak = LEAK_REGEX.search(page_source)
                self.assertIsNone(
                    leak,
                    f"Page leaked debug info after SQL injection: {leak.group(0) if leak else ''}",
                )
                has_results = len(self.driver.find_elements(By.CSS_SELECTOR, COURSE_INFO_CSS)) > 0
                has_no_courses = NO_COURSES_TEXT in self.driver.find_element(By.TAG_NAME, "body").text
                self.assertTrue(
                    has_results or has_no_courses,
                    f"SQL injection input caused unexpected page state: {payload!r}",
                )

    # ── Security: Long input ──────────────────────────────────────────

    def test_security_long_input_no_crash(self):
        """A 300-character search string must not crash the page or leak debug info."""
        self.open_courses_page()
        long_str = "A" * 300
        self._type_into(SEARCH_INPUT_NAME, long_str)
        self._wait_for_search_results(timeout=15)

        page_source = self.driver.page_source or ""
        leak = LEAK_REGEX.search(page_source)
        self.assertIsNone(
            leak,
            f"Page leaked debug info after long input: {leak.group(0) if leak else ''}",
        )
        has_results = len(self.driver.find_elements(By.CSS_SELECTOR, COURSE_INFO_CSS)) > 0
        has_no_courses = NO_COURSES_TEXT in self.driver.find_element(By.TAG_NAME, "body").text
        self.assertTrue(
            has_results or has_no_courses,
            "Long input caused unexpected page state",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
