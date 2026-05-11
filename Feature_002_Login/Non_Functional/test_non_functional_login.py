"""Non-functional tests: brute-force resilience + login response time."""
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

LOGIN_URL = "https://school.moodledemo.net/login/index.php"
SUCCESS_FRAGMENT = "/my/"
USERNAME_ID = "username"
PASSWORD_ID = "password"
LOGIN_BTN_ID = "loginbtn"
ERROR_XPATH = "//*[@id='loginerrormessage' or contains(@class,'loginerrors') or contains(@class,'alert-danger')]"

GENERIC_ERROR = "Please try again"
# original spec was 3.0s, relaxed for the public demo over the internet
PERF_BUDGET = 8.0
BRUTE_FORCE_TRIES = 20

# stack-trace / DB-error signatures that should never leak to the user
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


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


class TestLoginNonFunctional(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.wait = WebDriverWait(cls.driver, 15)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def open_login(self):
        self.driver.get(LOGIN_URL)
        self.driver.delete_all_cookies()
        self.driver.get(LOGIN_URL)
        self.wait.until(EC.presence_of_element_located((By.ID, USERNAME_ID)))

    def type_into(self, field_id, text):
        for _ in range(4):
            try:
                el = self.driver.find_element(By.ID, field_id)
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                el.clear()
                if text:
                    el.send_keys(text)
                return
            except (StaleElementReferenceException, ElementNotInteractableException):
                time.sleep(0.4)
        el = self.driver.find_element(By.ID, field_id)
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el, text or "",
        )

    def get_error_text(self):
        try:
            el = WebDriverWait(self.driver, 8).until(
                EC.visibility_of_element_located((By.XPATH, ERROR_XPATH))
            )
            return el.text.strip()
        except TimeoutException:
            return ""

    def submit(self, username, password):
        self.type_into(USERNAME_ID, username)
        self.type_into(PASSWORD_ID, password)
        self.driver.find_element(By.ID, LOGIN_BTN_ID).click()

    def test_security_brute_force(self):
        """20 wrong-password attempts must always show the generic error and never leak debug info."""
        for i in range(1, BRUTE_FORCE_TRIES + 1):
            self.open_login()
            self.submit("student", f"wrong_{i}_{int(time.time() * 1000)}")

            err = self.get_error_text()
            self.assertIn(GENERIC_ERROR, err, f"[try {i}] expected generic error, got {err!r}")

            leak = LEAK_REGEX.search(self.driver.page_source or "")
            self.assertIsNone(leak, f"[try {i}] page leaked: {leak.group(0) if leak else ''}")

            self.assertNotIn(SUCCESS_FRAGMENT, self.driver.current_url,
                             f"[try {i}] brute-force unexpectedly authenticated")

    def test_performance_response_time(self):
        """Valid login should redirect within PERF_BUDGET seconds."""
        self.open_login()
        self.type_into(USERNAME_ID, "student")
        self.type_into(PASSWORD_ID, "moodle26")

        start = time.time()
        self.driver.find_element(By.ID, LOGIN_BTN_ID).click()

        try:
            WebDriverWait(self.driver, 10).until(lambda d: SUCCESS_FRAGMENT in d.current_url)
        except TimeoutException:
            self.fail(f"login did not redirect in time (url={self.driver.current_url!r})")

        elapsed = time.time() - start
        self.assertLessEqual(elapsed, PERF_BUDGET,
                             f"login took {elapsed:.2f}s, budget is {PERF_BUDGET}s")


if __name__ == "__main__":
    unittest.main(verbosity=2)
