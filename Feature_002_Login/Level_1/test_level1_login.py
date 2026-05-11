"""Level 1: data-driven login tests. Locators hard-coded, data from CSV."""
import csv
import os
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
USERNAME_ID = "username"
PASSWORD_ID = "password"
LOGIN_BTN_ID = "loginbtn"
ERROR_XPATH = "//*[@id='loginerrormessage' or contains(@class,'loginerrors') or contains(@class,'alert-danger')]"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "login_data.csv")


def read_data():
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("tc_id")]


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


class TestLogin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.wait = WebDriverWait(cls.driver, 15)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def open_login(self):
        # wipe previous session so a successful login doesn't redirect us away
        self.driver.get(LOGIN_URL)
        self.driver.delete_all_cookies()
        self.driver.get(LOGIN_URL)
        self.wait.until(EC.presence_of_element_located((By.ID, USERNAME_ID)))

    def type_into(self, field_id, text):
        # retry: page may still be settling, or an overlay may briefly cover the field
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
        # last resort: set value via JS so an overlay can't block the test
        el = self.driver.find_element(By.ID, field_id)
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el, text or "",
        )

    def get_error_text(self):
        try:
            el = WebDriverWait(self.driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, ERROR_XPATH))
            )
            return el.text.strip()
        except TimeoutException:
            return ""

    def run_case(self, row):
        tc = row["tc_id"]
        self.open_login()
        self.type_into(USERNAME_ID, row["username"])
        self.type_into(PASSWORD_ID, row["password"])
        self.driver.find_element(By.ID, LOGIN_BTN_ID).click()

        kind = row["expected_type"].upper()
        expected = row["expected_value"]

        if kind == "URL":
            try:
                self.wait.until(lambda d: expected in d.current_url)
            except TimeoutException:
                pass
            self.assertIn(expected, self.driver.current_url, f"[{tc}] URL mismatch")

        elif kind == "ERROR":
            err = self.get_error_text()
            if err:
                self.assertIn(expected, err, f"[{tc}] error text mismatch: {err!r}")
            else:
                # HTML5 blocked submit (e.g. empty required field) — make sure we stayed
                url = self.driver.current_url
                self.assertIn("login/index.php", url, f"[{tc}] should still be on login")
                self.assertNotIn("/my/", url, f"[{tc}] should not be authenticated")
        else:
            self.fail(f"[{tc}] unknown expected_type {kind!r}")


def make_test(row):
    def t(self):
        self.run_case(row)
    t.__doc__ = f"{row['tc_id']} ({row['expected_type'].upper()})"
    return t


for r in read_data():
    setattr(TestLogin, "test_" + r["tc_id"].replace("-", "_"), make_test(r))


if __name__ == "__main__":
    unittest.main(verbosity=2)
