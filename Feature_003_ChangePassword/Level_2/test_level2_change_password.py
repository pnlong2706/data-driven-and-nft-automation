# -*- coding: utf-8 -*-
"""Level 2: fully data-driven. URLs and locators all come from elements_config.csv."""
import csv
import os
import unittest

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException

BY_MAP = {
    "ID":               By.ID,
    "XPATH":            By.XPATH,
    "CSS_SELECTOR":     By.CSS_SELECTOR,
    "LINK_TEXT":        By.LINK_TEXT,
    "NAME":             By.NAME,
    "CLASS_NAME":       By.CLASS_NAME,
    "TAG_NAME":         By.TAG_NAME,
    "PARTIAL_LINK_TEXT": By.PARTIAL_LINK_TEXT,
}

USERNAME      = "test_password_change"
BASE_PASSWORD = "moodle26"

TIMEOUT       = 20
HERE          = os.path.dirname(os.path.abspath(__file__))
DATA_FILE     = os.path.join(HERE, "change_password_data.csv")
ELEMENTS_FILE = os.path.join(HERE, "elements_config.csv")


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


def _load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_elements(path):
    urls     = {}
    locators = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name  = row["element_name"]
            ltype = row["locator_type"].strip()
            lval  = row["locator_value"].strip()
            if ltype == "URL":
                urls[name] = lval
            else:
                locators[name] = (BY_MAP[ltype], lval)
    return urls, locators


_URLS, _LOC = _load_elements(ELEMENTS_FILE)


def _login(driver, wait):
    driver.get(_URLS["login_url"])
    try:
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    except Exception:
        pass
    driver.delete_all_cookies()
    driver.get(_URLS["login_url"])
    wait.until(EC.presence_of_element_located(_LOC["username_field"])).clear()
    driver.find_element(*_LOC["username_field"]).send_keys(USERNAME)
    driver.find_element(*_LOC["password_field"]).clear()
    driver.find_element(*_LOC["password_field"]).send_keys(BASE_PASSWORD)
    driver.find_element(*_LOC["login_btn"]).click()
    wait.until(EC.presence_of_element_located(_LOC["user_menu"]))


def _navigate_to_change_password(driver, wait):
    driver.get(_URLS["preferences_url"])
    wait.until(EC.presence_of_element_located(_LOC["change_pw_link"])).click()
    wait.until(EC.url_contains(_URLS["change_pw_url"]))


def _fill_form_and_submit(driver, wait, current_pw, new_pw, confirm_pw):
    wait.until(EC.presence_of_element_located(_LOC["current_pw_field"])).clear()
    driver.find_element(*_LOC["current_pw_field"]).send_keys(current_pw)
    driver.find_element(*_LOC["new_pw1_field"]).clear()
    driver.find_element(*_LOC["new_pw1_field"]).send_keys(new_pw)
    driver.find_element(*_LOC["new_pw2_field"]).clear()
    driver.find_element(*_LOC["new_pw2_field"]).send_keys(confirm_pw)
    driver.find_element(*_LOC["submit_btn"]).click()


def _revert_password(driver, wait, changed_to):
    driver.get(_URLS["preferences_url"])
    wait.until(EC.presence_of_element_located(_LOC["change_pw_link"])).click()
    wait.until(EC.url_contains(_URLS["change_pw_url"]))
    wait.until(EC.presence_of_element_located(_LOC["current_pw_field"])).clear()
    driver.find_element(*_LOC["current_pw_field"]).send_keys(changed_to)
    driver.find_element(*_LOC["new_pw1_field"]).clear()
    driver.find_element(*_LOC["new_pw1_field"]).send_keys(BASE_PASSWORD)
    driver.find_element(*_LOC["new_pw2_field"]).clear()
    driver.find_element(*_LOC["new_pw2_field"]).send_keys(BASE_PASSWORD)
    driver.find_element(*_LOC["submit_btn"]).click()
    wait.until(EC.presence_of_element_located(_LOC["notice"]))


def _make_test(row):
    tc_id            = row["tc_id"]
    current_password = row["current_password"]
    new_password     = row["new_password"]
    confirm_password = row["confirm_password"]
    expected_type    = row["expected_type"]
    expected_value   = row["expected_value"]
    error_element_id = row.get("error_element_id", "").strip()

    def test_method(self):
        driver = self.driver
        wait   = WebDriverWait(driver, TIMEOUT,
                               ignored_exceptions=[StaleElementReferenceException])
        _login(driver, wait)
        _navigate_to_change_password(driver, wait)
        _fill_form_and_submit(driver, wait, current_password, new_password, confirm_password)

        if expected_type == "URL":
            notice = wait.until(EC.presence_of_element_located(_LOC["notice"]))
            self.assertIn("Password has been changed", notice.text,
                          f"[{tc_id}] Expected success notice, got: '{notice.text}'")
            self.assertIn(expected_value, driver.current_url,
                          f"[{tc_id}] Expected '{expected_value}' in URL, got: {driver.current_url}")
            _revert_password(driver, wait, new_password)
        else:
            err_locator = (By.ID, error_element_id)
            error_elem  = wait.until(EC.visibility_of_element_located(err_locator))
            self.assertEqual(expected_value, error_elem.text,
                             f"[{tc_id}] Expected error '{expected_value}', got: '{error_elem.text}'")

    test_method.__name__ = f"test_{tc_id.lower()}"
    return test_method


class TestChangePassword(unittest.TestCase):

    def setUp(self):
        self.driver = make_driver()
        self.driver.implicitly_wait(10)

    def tearDown(self):
        self.driver.quit()


for _row in _load_csv(DATA_FILE):
    _test_name = f"test_{_row['tc_id'].lower()}"
    setattr(TestChangePassword, _test_name, _make_test(_row))


if __name__ == "__main__":
    unittest.main(verbosity=2)
