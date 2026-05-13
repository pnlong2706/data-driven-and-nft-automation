# -*- coding: utf-8 -*-
"""
Non-Functional Tests: Feature 003 - Change Password

Suites:
  TestUsability        - navigability, form field visibility, label presence
  CompatibilityChrome  - full change-password flow on Chrome
  CompatibilityFirefox - full change-password flow on Firefox
"""
import csv
import os
import unittest

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException

LOGIN_URL       = "https://school.moodledemo.net/login/index.php"
PREFERENCES_URL = "https://school.moodledemo.net/user/preferences.php"

USERNAME      = "test_password_change"
BASE_PASSWORD = "moodle26"

TIMEOUT         = 20
MAX_CLICK_DEPTH = 5
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "change_password_data.csv")

LOC_USERNAME         = (By.ID,        "username")
LOC_PASSWORD         = (By.ID,        "password")
LOC_LOGIN_BTN        = (By.ID,        "loginbtn")
LOC_USER_MENU        = (By.ID,        "user-menu-toggle")
LOC_PREFERENCES_LINK = (By.LINK_TEXT, "Preferences")
LOC_CHANGE_PW_LINK   = (By.LINK_TEXT, "Change password")
LOC_CURRENT_PW       = (By.ID,        "id_password")
LOC_NEW_PW1          = (By.ID,        "id_newpassword1")
LOC_NEW_PW2          = (By.ID,        "id_newpassword2")
LOC_SUBMIT           = (By.ID,        "id_submitbutton")
LOC_NOTICE           = (By.ID,        "notice")


# driver factories 

def make_chrome_driver():
    opts = ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


def make_firefox_driver():
    opts = FirefoxOptions()
    opts.set_preference("browser.sessionstore.resume_from_crash", False)
    opts.set_preference("signon.rememberSignons", False)
    opts.set_preference("signon.autofillForms", False)
    return webdriver.Firefox(options=opts)


# shared helpers 

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
    wait.until(EC.url_changes(LOGIN_URL))
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


# Usability tests 

class TestUsability(unittest.TestCase):

    def setUp(self):
        self.driver = make_chrome_driver()
        self.driver.implicitly_wait(10)

    def tearDown(self):
        self.driver.quit()

    def test_click_depth_via_user_menu(self):
        """Change password form must be reachable within MAX_CLICK_DEPTH clicks."""
        driver = self.driver
        wait   = WebDriverWait(driver, TIMEOUT, ignored_exceptions=[StaleElementReferenceException])
        _login(driver, wait)
        start_url   = driver.current_url
        click_count = 0

        wait.until(EC.element_to_be_clickable(LOC_USER_MENU)).click()
        click_count += 1
        wait.until(EC.element_to_be_clickable(LOC_PREFERENCES_LINK)).click()
        click_count += 1
        wait.until(EC.url_contains("preferences.php"))
        wait.until(EC.element_to_be_clickable(LOC_CHANGE_PW_LINK)).click()
        click_count += 1
        wait.until(EC.url_contains("change_password.php"))

        print(f"\n[Usability] Click depth to Change Password: {click_count}/{MAX_CLICK_DEPTH} (from {start_url})")
        self.assertLessEqual(click_count, MAX_CLICK_DEPTH,
                             f"Click depth {click_count} exceeds threshold of {MAX_CLICK_DEPTH}.")

    def test_preferences_shortcut_in_user_menu(self):
        """'Preferences' must be directly visible in the user dropdown."""
        driver = self.driver
        wait   = WebDriverWait(driver, TIMEOUT, ignored_exceptions=[StaleElementReferenceException])
        _login(driver, wait)
        wait.until(EC.element_to_be_clickable(LOC_USER_MENU)).click()
        pref_link = wait.until(EC.visibility_of_element_located(LOC_PREFERENCES_LINK))
        self.assertTrue(pref_link.is_displayed(),
                        "[Usability] 'Preferences' link not visible in the user dropdown.")

    def test_change_password_form_fields_visible(self):
        """All three password fields and the submit button must be visible on the form."""
        driver = self.driver
        wait   = WebDriverWait(driver, TIMEOUT, ignored_exceptions=[StaleElementReferenceException])
        _login(driver, wait)
        driver.get(PREFERENCES_URL)
        wait.until(EC.element_to_be_clickable(LOC_CHANGE_PW_LINK)).click()
        wait.until(EC.url_contains("change_password.php"))
        for loc, label in [
            (LOC_CURRENT_PW, "Current password field"),
            (LOC_NEW_PW1,    "New password field"),
            (LOC_NEW_PW2,    "Confirm password field"),
            (LOC_SUBMIT,     "Submit button"),
        ]:
            elem = wait.until(EC.visibility_of_element_located(loc))
            self.assertTrue(elem.is_displayed(),
                            f"[Usability] '{label}' not visible on the Change Password form.")

    def test_form_fields_have_labels(self):
        """Each password input must have an associated <label> element."""
        driver = self.driver
        wait   = WebDriverWait(driver, TIMEOUT, ignored_exceptions=[StaleElementReferenceException])
        _login(driver, wait)
        driver.get(PREFERENCES_URL)
        wait.until(EC.element_to_be_clickable(LOC_CHANGE_PW_LINK)).click()
        wait.until(EC.url_contains("change_password.php"))
        for field_id, field_label in [
            ("id_password",     "Current password"),
            ("id_newpassword1", "New password"),
            ("id_newpassword2", "New password (again)"),
        ]:
            labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{field_id}']")
            self.assertTrue(len(labels) > 0 and labels[0].is_displayed(),
                            f"[Usability] No visible <label> found for '{field_label}' (id={field_id}).")


# Compatibility tests

def _make_compat_test(row):
    tc_id            = row["tc_id"]
    current_password = row["current_password"]
    new_password     = row["new_password"]
    confirm_password = row["confirm_password"]
    expected_type    = row["expected_type"]
    expected_value   = row["expected_value"]
    error_element_id = row.get("error_element_id", "").strip()

    def test_method(self):
        driver = self.driver
        wait   = WebDriverWait(driver, TIMEOUT, ignored_exceptions=[StaleElementReferenceException])
        _login(driver, wait)
        _navigate_to_change_password(driver, wait)
        _fill_form_and_submit(driver, wait, current_password, new_password, confirm_password)

        if expected_type == "URL":
            notice = wait.until(EC.presence_of_element_located(LOC_NOTICE))
            self.assertIn("Password has been changed", notice.text,
                          f"[{tc_id}][{self.BROWSER}] Expected success notice, got: '{notice.text}'")
            self.assertIn(expected_value, driver.current_url,
                          f"[{tc_id}][{self.BROWSER}] Expected '{expected_value}' in URL, "
                          f"got: {driver.current_url}")
            _revert_password(driver, wait, new_password)
        else:
            err_locator = (By.ID, error_element_id)
            error_elem  = wait.until(EC.visibility_of_element_located(err_locator))
            self.assertEqual(expected_value, error_elem.text,
                             f"[{tc_id}][{self.BROWSER}] Expected error '{expected_value}', "
                             f"got: '{error_elem.text}'")

    test_method.__name__ = f"test_{tc_id.lower()}"
    return test_method


class _CompatBase(unittest.TestCase):
    BROWSER = None

    def setUp(self):
        last_exc = None
        for _ in range(2):
            try:
                if self.BROWSER == "chrome":
                    self.driver = make_chrome_driver()
                else:
                    self.driver = make_firefox_driver()
                self.driver.implicitly_wait(10)
                return
            except Exception as exc:
                last_exc = exc
        self.skipTest(f"Browser '{self.BROWSER}' unavailable: {last_exc}")

    def tearDown(self):
        if hasattr(self, "driver"):
            self.driver.quit()


class CompatibilityChrome(_CompatBase):
    BROWSER = "chrome"


class CompatibilityFirefox(_CompatBase):
    BROWSER = "firefox"


for _row in _load_csv(DATA_FILE):
    _test_name = f"test_{_row['tc_id'].lower()}"
    _test_fn   = _make_compat_test(_row)
    setattr(CompatibilityChrome,  _test_name, _test_fn)
    setattr(CompatibilityFirefox, _test_name, _test_fn)


if __name__ == "__main__":
    unittest.main(verbosity=2)
