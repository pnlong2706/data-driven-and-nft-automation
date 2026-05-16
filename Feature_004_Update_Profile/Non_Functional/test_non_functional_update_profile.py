"""Non-functional tests: performance + security for profile update."""
import re
import time
import unittest

from selenium import webdriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoAlertPresentException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# --- constants ---------------------------------------------------------------
LOGIN_URL = "https://school.moodledemo.net/login/index.php"
PROFILE_EDIT_URL = "https://school.moodledemo.net/user/edit.php"
PROFILE_VIEW_URL = "https://school.moodledemo.net/user/profile.php"

LOGIN_USER_ID = "username"
LOGIN_PASS_ID = "password"
LOGIN_BTN_ID = "loginbtn"
LOGIN_OK_FRAG = "/my/"

FIRSTNAME_ID = "id_firstname"
LASTNAME_ID = "id_lastname"
EMAIL_ID = "id_email"
SUBMIT_BTN_ID = "id_submitbutton"
ERROR_XPATH = (
    "//span[contains(@class,'error')]"
    "|//div[contains(@class,'alert-danger')]"
    "|//div[contains(@class,'form-control-feedback') and contains(@class,'invalid-feedback')]"
)

TEST_USER = "student"
TEST_PASS = "moodle26"

# performance budget (seconds) – relaxed for a public demo over the internet
PERF_BUDGET = 8.0

# patterns that should NEVER appear in a user-facing page
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


class TestUpdateProfileNonFunctional(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.wait = WebDriverWait(cls.driver, 15)
        cls._login()
        cls._save_originals()

    @classmethod
    def tearDownClass(cls):
        cls._restore_originals()
        cls.driver.quit()

    # -- helpers --------------------------------------------------------------
    @classmethod
    def _login(cls, retries=3):
        for attempt in range(1, retries + 1):
            try:
                cls.driver.get(LOGIN_URL)
                cls.driver.delete_all_cookies()
                cls.driver.get(LOGIN_URL)
                WebDriverWait(cls.driver, 30).until(
                    EC.element_to_be_clickable((By.ID, LOGIN_USER_ID))
                )
                cls.driver.find_element(By.ID, LOGIN_USER_ID).clear()
                cls.driver.find_element(By.ID, LOGIN_USER_ID).send_keys(TEST_USER)
                WebDriverWait(cls.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, LOGIN_PASS_ID))
                )
                cls.driver.find_element(By.ID, LOGIN_PASS_ID).clear()
                cls.driver.find_element(By.ID, LOGIN_PASS_ID).send_keys(TEST_PASS)
                cls.driver.find_element(By.ID, LOGIN_BTN_ID).click()
                WebDriverWait(cls.driver, 30).until(lambda d: LOGIN_OK_FRAG in d.current_url)
                return
            except (TimeoutException, NoSuchElementException,
                    ElementNotInteractableException):
                if attempt == retries:
                    raise
                time.sleep(3)

    @classmethod
    def _save_originals(cls):
        cls.driver.get(PROFILE_EDIT_URL)
        WebDriverWait(cls.driver, 15).until(
            EC.presence_of_element_located((By.ID, FIRSTNAME_ID))
        )
        cls.orig = {
            "firstname": cls.driver.find_element(By.ID, FIRSTNAME_ID).get_attribute("value"),
            "lastname": cls.driver.find_element(By.ID, LASTNAME_ID).get_attribute("value"),
            "email": cls.driver.find_element(By.ID, EMAIL_ID).get_attribute("value"),
        }

    @classmethod
    def _restore_originals(cls):
        try:
            cls.driver.get(PROFILE_EDIT_URL)
            WebDriverWait(cls.driver, 15).until(
                EC.presence_of_element_located((By.ID, FIRSTNAME_ID))
            )
            for fid, val in [
                (FIRSTNAME_ID, cls.orig["firstname"]),
                (LASTNAME_ID, cls.orig["lastname"]),
                (EMAIL_ID, cls.orig["email"]),
            ]:
                el = cls.driver.find_element(By.ID, fid)
                el.clear()
                if val:
                    el.send_keys(val)
            cls.driver.find_element(By.ID, SUBMIT_BTN_ID).click()
            time.sleep(2)
        except Exception:
            pass

    def open_profile_edit(self):
        self.driver.get(PROFILE_EDIT_URL)
        self.wait.until(EC.presence_of_element_located((By.ID, FIRSTNAME_ID)))

    def type_into(self, field_id, text):
        for _ in range(4):
            try:
                el = self.driver.find_element(By.ID, field_id)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el
                )
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

    def click_submit(self):
        btn = self.driver.find_element(By.ID, SUBMIT_BTN_ID)
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        self.driver.execute_script(
            "var f=arguments[0].closest('form'); if(f) f.setAttribute('novalidate','true');",
            btn,
        )
        btn.click()

    # -- NFR 1: Performance ---------------------------------------------------
    def test_performance_profile_update_time(self):
        """Valid profile update should complete within PERF_BUDGET seconds."""
        self.open_profile_edit()
        current_fn = self.driver.find_element(By.ID, FIRSTNAME_ID).get_attribute("value")
        # make a small harmless change
        new_fn = current_fn.rstrip() + " "
        self.type_into(FIRSTNAME_ID, new_fn)

        start = time.time()
        self.click_submit()

        try:
            # wait until we leave the edit page or see a success notification
            WebDriverWait(self.driver, 15).until(
                lambda d: "edit.php" not in d.current_url
                or d.find_elements(By.XPATH, "//div[contains(@class,'alert-success')]")
            )
        except TimeoutException:
            self.fail(f"profile update did not complete (url={self.driver.current_url!r})")

        elapsed = time.time() - start
        self.assertLessEqual(
            elapsed, PERF_BUDGET,
            f"profile update took {elapsed:.2f}s, budget is {PERF_BUDGET}s",
        )

        # restore
        self._restore_originals()

    # -- NFR 2: Security – XSS protection ------------------------------------
    def test_security_xss_in_firstname(self):
        """XSS payload in first-name must not execute or appear raw in the page."""
        XSS = "<script>alert('XSS')</script>"

        self.open_profile_edit()
        self.type_into(FIRSTNAME_ID, XSS)
        self.click_submit()
        time.sleep(2)

        # 1) no JS alert should have fired
        try:
            self.driver.switch_to.alert
            self.driver.switch_to.alert.dismiss()
            self.fail("XSS alert appeared — the application is vulnerable!")
        except NoAlertPresentException:
            pass  # good

        # 2) navigate to profile view and check the rendered page
        self.driver.get(PROFILE_VIEW_URL)
        time.sleep(2)
        src = self.driver.page_source or ""

        # the raw <script> tag must not appear unescaped
        self.assertNotIn(
            "<script>alert('XSS')</script>", src,
            "Raw XSS payload found in rendered profile page",
        )

        # 3) no debug/stack-trace info should leak
        leak = LEAK_REGEX.search(src)
        self.assertIsNone(
            leak,
            f"Page leaked internal info: {leak.group(0) if leak else ''}",
        )

        # restore
        self._restore_originals()

    # -- NFR 3: Security – no debug info on invalid input ---------------------
    def test_security_no_debug_leak_on_error(self):
        """Submitting invalid data must show a user-friendly error, never debug info."""
        self.open_profile_edit()
        # clear required field to trigger server error
        self.type_into(FIRSTNAME_ID, "")
        self.click_submit()
        time.sleep(2)

        src = self.driver.page_source or ""
        leak = LEAK_REGEX.search(src)
        self.assertIsNone(
            leak,
            f"Page leaked internal info on error: {leak.group(0) if leak else ''}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
