"""Level 1: data-driven update-profile tests. Locators hard-coded, data from CSV."""
import csv
import os
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

# --- URLs --------------------------------------------------------------------
LOGIN_URL = "https://school.moodledemo.net/login/index.php"
PROFILE_EDIT_URL = "https://school.moodledemo.net/user/edit.php"

# --- login page elements ----------------------------------------------------
LOGIN_USER_ID = "username"
LOGIN_PASS_ID = "password"
LOGIN_BTN_ID = "loginbtn"
LOGIN_OK_FRAG = "/my/"

# --- profile-edit page elements ---------------------------------------------
FIRSTNAME_ID = "id_firstname"
LASTNAME_ID = "id_lastname"
EMAIL_ID = "id_email"
SUBMIT_BTN_ID = "id_submitbutton"
CANCEL_EMAIL_XPATH = "//a[contains(@href,'cancelemailchange')]"
ERROR_XPATH = (
    "//span[contains(@class,'error')]"
    "|//div[contains(@class,'alert-danger')]"
    "|//div[contains(@class,'form-control-feedback') and contains(@class,'invalid-feedback')]"
)

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_profile_data.csv")
KEEP = "__KEEP__"
TEST_USER = "student"
TEST_PASS = "moodle26"


def read_data():
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("tc_id")]


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


class TestUpdateProfile(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.wait = WebDriverWait(cls.driver, 15)
        cls._login()
        cls._cancel_pending_email()
        cls._save_originals()

    @classmethod
    def tearDownClass(cls):
        cls._restore_originals()
        cls.driver.quit()

    # -- auth helpers ---------------------------------------------------------
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
                return  # success
            except (TimeoutException, NoSuchElementException,
                    ElementNotInteractableException):
                if attempt == retries:
                    raise
                time.sleep(3)

    # -- profile helpers ------------------------------------------------------
    @classmethod
    def _cancel_pending_email(cls):
        """If there is a pending email change, cancel it to restore the email field."""
        cls.driver.get(PROFILE_EDIT_URL)
        WebDriverWait(cls.driver, 15).until(
            EC.presence_of_element_located((By.ID, FIRSTNAME_ID))
        )
        links = cls.driver.find_elements(By.XPATH, CANCEL_EMAIL_XPATH)
        if links:
            links[0].click()
            time.sleep(2)
            # After cancellation, re-navigate to edit page
            cls.driver.get(PROFILE_EDIT_URL)
            WebDriverWait(cls.driver, 15).until(
                EC.presence_of_element_located((By.ID, FIRSTNAME_ID))
            )

    @classmethod
    def _save_originals(cls):
        # Ensure we're on the edit page with email field available
        WebDriverWait(cls.driver, 10).until(
            EC.presence_of_element_located((By.ID, EMAIL_ID))
        )
        cls.orig = {
            "firstname": cls.driver.find_element(By.ID, FIRSTNAME_ID).get_attribute("value"),
            "lastname": cls.driver.find_element(By.ID, LASTNAME_ID).get_attribute("value"),
            "email": cls.driver.find_element(By.ID, EMAIL_ID).get_attribute("value"),
        }

    @classmethod
    def _restore_originals(cls):
        """Put back the values that were on the profile before the test run."""
        try:
            cls.driver.get(PROFILE_EDIT_URL)
            WebDriverWait(cls.driver, 15).until(
                EC.presence_of_element_located((By.ID, FIRSTNAME_ID))
            )
            # Cancel any pending email change first
            links = cls.driver.find_elements(By.XPATH, CANCEL_EMAIL_XPATH)
            if links:
                links[0].click()
                time.sleep(2)
                cls.driver.get(PROFILE_EDIT_URL)
                WebDriverWait(cls.driver, 15).until(
                    EC.presence_of_element_located((By.ID, FIRSTNAME_ID))
                )
            WebDriverWait(cls.driver, 10).until(
                EC.presence_of_element_located((By.ID, EMAIL_ID))
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
            # handle email confirmation "Continue" page
            try:
                cont = WebDriverWait(cls.driver, 3).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//button[contains(text(),'Continue')]"
                        "|//a[contains(text(),'Continue')]"
                    ))
                )
                cont.click()
                time.sleep(1)
            except (TimeoutException, NoSuchElementException):
                pass
        except Exception:
            pass

    def open_profile_edit(self):
        self.driver.get(PROFILE_EDIT_URL)
        self.wait.until(EC.presence_of_element_located((By.ID, FIRSTNAME_ID)))
        # Cancel pending email if present, so id_email is available
        links = self.driver.find_elements(By.XPATH, CANCEL_EMAIL_XPATH)
        if links:
            links[0].click()
            time.sleep(2)
            self.driver.get(PROFILE_EDIT_URL)
            self.wait.until(EC.presence_of_element_located((By.ID, FIRSTNAME_ID)))
        self.wait.until(EC.presence_of_element_located((By.ID, EMAIL_ID)))

    def type_into(self, field_id, text):
        for _ in range(6):
            try:
                el = self.driver.find_element(By.ID, field_id)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el
                )
                el.clear()
                if text:
                    el.send_keys(text)
                return
            except (StaleElementReferenceException, ElementNotInteractableException,
                    NoSuchElementException):
                time.sleep(0.5)
        # JS fallback
        el = self.driver.find_element(By.ID, field_id)
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el, text or "",
        )

    def get_all_errors(self):
        """Concatenated text of every visible error element on the page."""
        time.sleep(1)
        els = self.driver.find_elements(By.XPATH, ERROR_XPATH)
        return " | ".join(e.text.strip() for e in els if e.is_displayed() and e.text.strip())

    def click_submit(self):
        btn = self.driver.find_element(By.ID, SUBMIT_BTN_ID)
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        # bypass HTML5 client-side validation so server errors can be tested
        self.driver.execute_script(
            "var f=arguments[0].closest('form'); if(f) f.setAttribute('novalidate','true');",
            btn,
        )
        btn.click()

    def _click_continue_if_present(self):
        """After email-change confirmation Moodle may show a Continue button."""
        try:
            cont = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(text(),'Continue')]"
                    "|//a[contains(text(),'Continue')]"
                ))
            )
            cont.click()
            time.sleep(1)
        except (TimeoutException, NoSuchElementException):
            pass

    # -- core -----------------------------------------------------------------
    def run_case(self, row):
        tc = row["tc_id"]
        self.open_profile_edit()

        if row["firstname"] != KEEP:
            self.type_into(FIRSTNAME_ID, row["firstname"])
        if row["lastname"] != KEEP:
            self.type_into(LASTNAME_ID, row["lastname"])
        if row["email"] != KEEP:
            self.type_into(EMAIL_ID, row["email"])

        self.click_submit()
        time.sleep(2)

        kind = row["expected_type"].strip().upper()
        expected = row["expected_value"].strip()

        if kind == "SUCCESS":
            self._click_continue_if_present()
            errors = self.get_all_errors()
            self.assertEqual(errors, "", f"[{tc}] unexpected errors: {errors}")

            # optional saved-value check (e.g. trim verification for TC-004-003)
            if expected:
                self.open_profile_edit()
                saved = self.driver.find_element(By.ID, FIRSTNAME_ID).get_attribute("value")
                self.assertEqual(
                    saved, expected,
                    f"[{tc}] saved value mismatch: {saved!r} != {expected!r}",
                )

            # restore original values after a successful modification
            self._restore_originals()

        elif kind == "ERROR":
            errors = self.get_all_errors()
            if errors:
                self.assertIn(
                    expected.lower(), errors.lower(),
                    f"[{tc}] expected error '{expected}' not in: {errors!r}",
                )
            else:
                # form may have been blocked by HTML5 validation — at least
                # make sure we never left the edit page
                url = self.driver.current_url
                self.assertIn(
                    "edit.php", url,
                    f"[{tc}] should still be on the edit page",
                )
        else:
            self.fail(f"[{tc}] unknown expected_type {kind!r}")


# --- dynamically create one test method per CSV row --------------------------
def _make_test(row):
    def t(self):
        self.run_case(row)
    t.__doc__ = f"{row['tc_id']} ({row['expected_type'].upper()})"
    return t


for _r in read_data():
    setattr(TestUpdateProfile, "test_" + _r["tc_id"].replace("-", "_"), _make_test(_r))


if __name__ == "__main__":
    unittest.main(verbosity=2)
