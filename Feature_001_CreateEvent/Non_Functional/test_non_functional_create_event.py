"""Non-functional tests for Create Event: response-time + malicious-input resilience."""
import re
import time
import unittest

from selenium import webdriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://school.moodledemo.net"
LOGIN_URL = f"{BASE_URL}/login/index.php"
CALENDAR_MONTH_URL = f"{BASE_URL}/calendar/view.php?view=month"

USERNAME = "student"
PASSWORD = "moodle26"
TIMEOUT = 20
PERF_BUDGET = 15.0

XSS_PAYLOADS = [
    '<script>alert("xss")</script>',
    '"><img src=x onerror=alert(1)>',
    "'\"><svg/onload=alert(1)>",
]
SQL_INJECTION_PAYLOADS = [
    "' OR 1=1 --",
    "'; DROP TABLE mdl_event; --",
    '" UNION SELECT * FROM mdl_user --',
]

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

LOC_USERNAME = (By.ID, "username")
LOC_PASSWORD = (By.ID, "password")
LOC_LOGIN_BTN = (By.ID, "loginbtn")
LOC_LOGIN_ERROR = (
    By.XPATH,
    "//*[@id='loginerrormessage' or contains(@class,'loginerrors') or contains(@class,'alert-danger')]",
)
LOC_GUEST_ACCESS = (By.XPATH, "//*[contains(normalize-space(.), 'guest access')]")
LOC_LOGIN_LINK = (
    By.XPATH,
    "//a[contains(@href, '/login/index.php')][contains(normalize-space(.), 'Log in')]",
)
LOC_NEW_EVENT_BTN = (By.XPATH, "//button[contains(@data-action,'new-event-button')]")
LOC_EVENT_NAME = (By.ID, "id_name")
LOC_SAVE_BTN = (By.XPATH, "//button[contains(@data-action,'save')]")


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=opts)


def xpath_literal(value):
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ', \'"\', '.join(f'"{p}"' for p in parts) + ")"


class TestCreateEventNonFunctional(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.wait = WebDriverWait(cls.driver, TIMEOUT)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def _type_into(self, locator, text):
        for _ in range(4):
            try:
                el = self.driver.find_element(*locator)
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                el.clear()
                if text:
                    el.send_keys(text)
                return
            except (StaleElementReferenceException, ElementNotInteractableException):
                time.sleep(0.4)
        el = self.driver.find_element(*locator)
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el, text or "",
        )

    def _is_login_page(self):
        if "/login/index.php" in self.driver.current_url:
            return True
        if self.driver.find_elements(*LOC_USERNAME):
            return True
        if self.driver.find_elements(*LOC_GUEST_ACCESS):
            return True
        return bool(self.driver.find_elements(*LOC_LOGIN_LINK))

    def _login(self):
        for attempt in range(2):
            self.driver.get(LOGIN_URL)
            self.wait.until(EC.presence_of_element_located(LOC_USERNAME))
            self._type_into(LOC_USERNAME, USERNAME)
            self._type_into(LOC_PASSWORD, PASSWORD)
            self.driver.find_element(*LOC_LOGIN_BTN).click()
            try:
                self.wait.until(lambda d: "/login/index.php" not in d.current_url)
                return
            except TimeoutException:
                if attempt == 0:
                    continue
                errors = self.driver.find_elements(*LOC_LOGIN_ERROR)
                if errors:
                    self.fail(f"Login failed: {errors[0].text.strip()}")
                self.fail("Login did not complete.")

    def _open_month(self):
        try:
            self.driver.get(CALENDAR_MONTH_URL)
        except TimeoutException:
            pass
        if self._is_login_page():
            self._login()
            self.driver.get(CALENDAR_MONTH_URL)
        self.wait.until(EC.presence_of_element_located(LOC_NEW_EVENT_BTN))

    def _create_event_and_wait(self, event_name, expect_exact_name_visible=True):
        self._open_month()
        self.wait.until(EC.element_to_be_clickable(LOC_NEW_EVENT_BTN)).click()
        self.wait.until(EC.visibility_of_element_located(LOC_EVENT_NAME))
        self._type_into(LOC_EVENT_NAME, event_name)

        started = time.time()
        self.driver.find_element(*LOC_SAVE_BTN).click()

        self.wait.until(
            lambda d: d.find_elements(*LOC_NEW_EVENT_BTN) or d.find_elements(*LOC_EVENT_NAME)
        )
        if expect_exact_name_visible:
            event_xpath = f"//*[contains(normalize-space(.), {xpath_literal(event_name)})]"
            self.wait.until(EC.visibility_of_element_located((By.XPATH, event_xpath)))
        return time.time() - started

    def _assert_no_debug_leak(self):
        leak = LEAK_REGEX.search(self.driver.page_source or "")
        self.assertIsNone(leak, f"Page leaked debug info: {leak.group(0) if leak else ''}")

    def test_performance_create_event_response_time(self):
        """Saving a valid event should complete within PERF_BUDGET seconds."""
        event_name = f"NF_PERF_{int(time.time() * 1000)}"
        elapsed = self._create_event_and_wait(event_name)
        self.assertLessEqual(
            elapsed, PERF_BUDGET,
            f"Create-event flow took {elapsed:.2f}s, budget is {PERF_BUDGET}s",
        )

    def test_security_xss_payload_no_debug_leak(self):
        """XSS payloads should not trigger server-side debug/DB leak signatures."""
        for i, payload in enumerate(XSS_PAYLOADS, start=1):
            with self.subTest(payload=payload):
                event_name = f"NF_XSS_{i}_{int(time.time() * 1000)} {payload}"
                self._create_event_and_wait(event_name, expect_exact_name_visible=False)
                self._assert_no_debug_leak()
                self.assertIn("/calendar/", self.driver.current_url)

    def test_security_sql_injection_no_error_leak(self):
        """SQLi-like payloads should not produce DB/debug leak signatures."""
        for i, payload in enumerate(SQL_INJECTION_PAYLOADS, start=1):
            with self.subTest(payload=payload):
                event_name = f"NF_SQL_{i}_{int(time.time() * 1000)} {payload}"
                self._create_event_and_wait(event_name)
                self._assert_no_debug_leak()
                self.assertIn("/calendar/", self.driver.current_url)

    def test_security_long_input_no_crash(self):
        """A long event name should not crash the page or leak debug details."""
        long_name = f"NF_LONG_{int(time.time() * 1000)}_" + ("A" * 300)
        self._create_event_and_wait(long_name)
        self._assert_no_debug_leak()
        self.assertIn("/calendar/", self.driver.current_url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
