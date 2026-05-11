"""Level 2: fully data-driven. URLs and locators all come from elements_config.csv."""
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

HERE = os.path.dirname(os.path.abspath(__file__))
ELEMENTS_FILE = os.path.join(HERE, "elements_config.csv")
DATA_FILE = os.path.join(HERE, "login_data.csv")

BY_MAP = {
    "ID": By.ID,
    "NAME": By.NAME,
    "XPATH": By.XPATH,
    "CSS": By.CSS_SELECTOR,
    "CLASS": By.CLASS_NAME,
}


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_elements():
    table = {}
    for row in load_csv(ELEMENTS_FILE):
        name = (row.get("element_name") or "").strip()
        if not name:
            continue
        table[name] = {
            "type": (row.get("locator_type") or "").strip().upper(),
            "value": (row.get("locator_value") or "").strip(),
        }
    return table


def load_data():
    return [r for r in load_csv(DATA_FILE) if r.get("tc_id")]


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


class TestLogin(unittest.TestCase):

    elements = load_elements()

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.wait = WebDriverWait(cls.driver, 15)
        cls.site_url = cls.elements["site_url"]["value"]
        cls.success_fragment = cls.elements["success_url_fragment"]["value"]
        cls.login_fragment = cls.elements["login_url_fragment"]["value"]

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def locator(self, name):
        e = self.elements[name]
        return BY_MAP[e["type"]], e["value"]

    def open_login(self):
        self.driver.get(self.site_url)
        self.driver.delete_all_cookies()
        self.driver.get(self.site_url)
        self.wait.until(EC.presence_of_element_located(self.locator("txt_username")))

    def type_into(self, name, text):
        for _ in range(4):
            try:
                el = self.driver.find_element(*self.locator(name))
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                el.clear()
                if text:
                    el.send_keys(text)
                return
            except (StaleElementReferenceException, ElementNotInteractableException):
                time.sleep(0.4)
        el = self.driver.find_element(*self.locator(name))
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el, text or "",
        )

    def get_error_text(self):
        try:
            el = WebDriverWait(self.driver, 5).until(
                EC.visibility_of_element_located(self.locator("lbl_error"))
            )
            return el.text.strip()
        except TimeoutException:
            return ""

    def run_case(self, row):
        tc = row["tc_id"]
        self.open_login()
        self.type_into("txt_username", row["username"])
        self.type_into("txt_password", row["password"])
        self.driver.find_element(*self.locator("btn_login")).click()

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
                url = self.driver.current_url
                self.assertIn(self.login_fragment, url, f"[{tc}] should still be on login")
                self.assertNotIn(self.success_fragment, url, f"[{tc}] should not be authenticated")
        else:
            self.fail(f"[{tc}] unknown expected_type {kind!r}")


def make_test(row):
    def t(self):
        self.run_case(row)
    t.__doc__ = f"{row['tc_id']} ({row['expected_type'].upper()})"
    return t


for r in load_data():
    setattr(TestLogin, "test_" + r["tc_id"].replace("-", "_"), make_test(r))


if __name__ == "__main__":
    unittest.main(verbosity=2)
