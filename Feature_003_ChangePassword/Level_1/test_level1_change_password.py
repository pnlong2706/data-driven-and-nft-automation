# -*- coding: utf-8 -*-
"""Level 1: data-driven change-password tests. Locators hard-coded, data from CSV."""
import csv
import os
import unittest

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException

LOGIN_URL       = "https://school.moodledemo.net/login/index.php"
PREFERENCES_URL = "https://school.moodledemo.net/user/preferences.php"

USERNAME      = "test_password_change"
BASE_PASSWORD = "moodle26"

TIMEOUT   = 20
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "change_password_data.csv")

LOC_USERNAME       = (By.ID,        "username")
LOC_PASSWORD       = (By.ID,        "password")
LOC_LOGIN_BTN      = (By.ID,        "loginbtn")
LOC_USER_MENU      = (By.ID,        "user-menu-toggle")
LOC_CHANGE_PW_LINK = (By.LINK_TEXT, "Change password")
LOC_CURRENT_PW     = (By.ID,        "id_password")
LOC_NEW_PW1        = (By.ID,        "id_newpassword1")
LOC_NEW_PW2        = (By.ID,        "id_newpassword2")
LOC_SUBMIT         = (By.ID,        "id_submitbutton")
LOC_NOTICE         = (By.ID,        "notice")


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


def _load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _login(driver, wait):
    driver.get(LOGIN_URL)
    try:
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    except Exception:
        pass
    driver.delete_all_cookies()
    driver.get(LOGIN_URL)
    wait.until(EC.presence_of_element_located(LOC_USERNAME)).clear()
    driver.find_element(*LOC_USERNAME).send_keys(USERNAME)
    driver.find_element(*LOC_PASSWORD).clear()
    driver.find_element(*LOC_PASSWORD).send_keys(BASE_PASSWORD)
    driver.find_element(*LOC_LOGIN_BTN).click()
    wait.until(EC.presence_of_element_located(LOC_USER_MENU))


def _navigate_to_change_password(driver, wait):
    driver.get(PREFERENCES_URL)
    wait.until(EC.presence_of_element_located(LOC_CHANGE_PW_LINK)).click()
    wait.until(EC.url_contains("change_password.php"))


def _fill_form_and_submit(driver, wait, current_pw, new_pw, confirm_pw):
    wait.until(EC.presence_of_element_located(LOC_CURRENT_PW)).clear()
    driver.find_element(*LOC_CURRENT_PW).send_keys(current_pw)
    driver.find_element(*LOC_NEW_PW1).clear()
    driver.find_element(*LOC_NEW_PW1).send_keys(new_pw)
    driver.find_element(*LOC_NEW_PW2).clear()
    driver.find_element(*LOC_NEW_PW2).send_keys(confirm_pw)
    driver.find_element(*LOC_SUBMIT).click()


def _revert_password(driver, wait, changed_to):
    driver.get(PREFERENCES_URL)
    wait.until(EC.presence_of_element_located(LOC_CHANGE_PW_LINK)).click()
    wait.until(EC.url_contains("change_password.php"))
    wait.until(EC.presence_of_element_located(LOC_CURRENT_PW)).clear()
    driver.find_element(*LOC_CURRENT_PW).send_keys(changed_to)
    driver.find_element(*LOC_NEW_PW1).clear()
    driver.find_element(*LOC_NEW_PW1).send_keys(BASE_PASSWORD)
    driver.find_element(*LOC_NEW_PW2).clear()
    driver.find_element(*LOC_NEW_PW2).send_keys(BASE_PASSWORD)
    driver.find_element(*LOC_SUBMIT).click()
    wait.until(EC.presence_of_element_located(LOC_NOTICE))


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
            notice = wait.until(EC.presence_of_element_located(LOC_NOTICE))
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
