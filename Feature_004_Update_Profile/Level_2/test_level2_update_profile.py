"""Level 2: fully data-driven. URLs and locators all come from elements_config.csv."""
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

HERE = os.path.dirname(os.path.abspath(__file__))
ELEMENTS_FILE = os.path.join(HERE, "elements_config.csv")
DATA_FILE = os.path.join(HERE, "update_profile_data.csv")

KEEP = "__KEEP__"
TEST_USER = "student"
TEST_PASS = "moodle26"

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


class TestUpdateProfile(unittest.TestCase):

    elements = load_elements()

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.wait = WebDriverWait(cls.driver, 15)
        cls.login_url = cls.elements["login_url"]["value"]
        cls.profile_edit_url = cls.elements["profile_edit_url"]["value"]
        cls.login_ok_frag = cls.elements["login_success_fragment"]["value"]
        cls.edit_frag = cls.elements["edit_url_fragment"]["value"]
        cls._login()
        cls._cancel_pending_email()
        cls._save_originals()

    @classmethod
    def tearDownClass(cls):
        cls._restore_originals()
        cls.driver.quit()

    def locator(self, name):
        e = self.elements[name]
        return BY_MAP[e["type"]], e["value"]

    # -- auth -----------------------------------------------------------------
    @classmethod
    def _login(cls, retries=3):
        d = cls.driver
        el = cls.elements
        by_user = BY_MAP[el["txt_login_username"]["type"]]
        val_user = el["txt_login_username"]["value"]
        by_pass = BY_MAP[el["txt_login_password"]["type"]]
        val_pass = el["txt_login_password"]["value"]
        by_btn = BY_MAP[el["btn_login"]["type"]]
        val_btn = el["btn_login"]["value"]

        for attempt in range(1, retries + 1):
            try:
                d.get(cls.login_url)
                d.delete_all_cookies()
                d.get(cls.login_url)
                WebDriverWait(d, 30).until(EC.element_to_be_clickable((by_user, val_user)))
                d.find_element(by_user, val_user).clear()
                d.find_element(by_user, val_user).send_keys(TEST_USER)
                WebDriverWait(d, 10).until(EC.element_to_be_clickable((by_pass, val_pass)))
                d.find_element(by_pass, val_pass).clear()
                d.find_element(by_pass, val_pass).send_keys(TEST_PASS)
                d.find_element(by_btn, val_btn).click()
                WebDriverWait(d, 30).until(lambda drv: cls.login_ok_frag in drv.current_url)
                return
            except (TimeoutException, NoSuchElementException,
                    ElementNotInteractableException):
                if attempt == retries:
                    raise
                time.sleep(3)

    # -- profile helpers ------------------------------------------------------
    @classmethod
    def _cancel_pending_email(cls):
        """If there is a pending email change, cancel it to restore the email field."""
        d = cls.driver
        el = cls.elements
        d.get(cls.profile_edit_url)
        loc_fn = (BY_MAP[el["txt_firstname"]["type"]], el["txt_firstname"]["value"])
        WebDriverWait(d, 15).until(EC.presence_of_element_located(loc_fn))
        loc_cancel = (BY_MAP[el["lnk_cancel_email"]["type"]], el["lnk_cancel_email"]["value"])
        links = d.find_elements(*loc_cancel)
        if links:
            links[0].click()
            time.sleep(2)
            d.get(cls.profile_edit_url)
            WebDriverWait(d, 15).until(EC.presence_of_element_located(loc_fn))

    @classmethod
    def _save_originals(cls):
        d = cls.driver
        el = cls.elements
        loc_fn = (BY_MAP[el["txt_firstname"]["type"]], el["txt_firstname"]["value"])
        loc_ln = (BY_MAP[el["txt_lastname"]["type"]], el["txt_lastname"]["value"])
        loc_em = (BY_MAP[el["txt_email"]["type"]], el["txt_email"]["value"])
        WebDriverWait(d, 10).until(EC.presence_of_element_located(loc_em))
        cls.orig = {
            "firstname": d.find_element(*loc_fn).get_attribute("value"),
            "lastname": d.find_element(*loc_ln).get_attribute("value"),
            "email": d.find_element(*loc_em).get_attribute("value"),
        }

    @classmethod
    def _restore_originals(cls):
        try:
            d = cls.driver
            el = cls.elements
            d.get(cls.profile_edit_url)
            loc_fn = (BY_MAP[el["txt_firstname"]["type"]], el["txt_firstname"]["value"])
            WebDriverWait(d, 15).until(EC.presence_of_element_located(loc_fn))
            # Cancel pending email if present
            loc_cancel = (BY_MAP[el["lnk_cancel_email"]["type"]], el["lnk_cancel_email"]["value"])
            links = d.find_elements(*loc_cancel)
            if links:
                links[0].click()
                time.sleep(2)
                d.get(cls.profile_edit_url)
                WebDriverWait(d, 15).until(EC.presence_of_element_located(loc_fn))
            loc_em = (BY_MAP[el["txt_email"]["type"]], el["txt_email"]["value"])
            WebDriverWait(d, 10).until(EC.presence_of_element_located(loc_em))
            for name, val in [
                ("txt_firstname", cls.orig["firstname"]),
                ("txt_lastname", cls.orig["lastname"]),
                ("txt_email", cls.orig["email"]),
            ]:
                loc = (BY_MAP[el[name]["type"]], el[name]["value"])
                fld = d.find_element(*loc)
                fld.clear()
                if val:
                    fld.send_keys(val)
            btn_loc = (BY_MAP[el["btn_submit"]["type"]], el["btn_submit"]["value"])
            d.find_element(*btn_loc).click()
            time.sleep(2)
            # handle email confirmation page
            try:
                loc_cont = (BY_MAP[el["btn_continue"]["type"]], el["btn_continue"]["value"])
                cont = WebDriverWait(d, 3).until(EC.element_to_be_clickable(loc_cont))
                cont.click()
                time.sleep(1)
            except (TimeoutException, NoSuchElementException):
                pass
        except Exception:
            pass

    def open_profile_edit(self):
        self.driver.get(self.profile_edit_url)
        self.wait.until(EC.presence_of_element_located(self.locator("txt_firstname")))
        # Cancel pending email if present
        links = self.driver.find_elements(*self.locator("lnk_cancel_email"))
        if links:
            links[0].click()
            time.sleep(2)
            self.driver.get(self.profile_edit_url)
            self.wait.until(EC.presence_of_element_located(self.locator("txt_firstname")))
        self.wait.until(EC.presence_of_element_located(self.locator("txt_email")))

    def type_into(self, name, text):
        for _ in range(6):
            try:
                el = self.driver.find_element(*self.locator(name))
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
        el = self.driver.find_element(*self.locator(name))
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el, text or "",
        )

    def get_all_errors(self):
        time.sleep(1)
        els = self.driver.find_elements(*self.locator("lbl_error"))
        return " | ".join(e.text.strip() for e in els if e.is_displayed() and e.text.strip())

    def click_submit(self):
        btn = self.driver.find_element(*self.locator("btn_submit"))
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        self.driver.execute_script(
            "var f=arguments[0].closest('form'); if(f) f.setAttribute('novalidate','true');",
            btn,
        )
        btn.click()

    def _click_continue_if_present(self):
        try:
            cont = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable(self.locator("btn_continue"))
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
            self.type_into("txt_firstname", row["firstname"])
            # verify field value was set (use JS as fallback if send_keys lost chars)
            actual = self.driver.find_element(*self.locator("txt_firstname")).get_attribute("value")
            if actual != row["firstname"]:
                el = self.driver.find_element(*self.locator("txt_firstname"))
                self.driver.execute_script(
                    "arguments[0].value = arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    el, row["firstname"],
                )
        if row["lastname"] != KEEP:
            self.type_into("txt_lastname", row["lastname"])
        if row["email"] != KEEP:
            self.type_into("txt_email", row["email"])

        self.click_submit()
        time.sleep(2)

        kind = row["expected_type"].strip().upper()
        expected = row["expected_value"].strip()

        if kind == "SUCCESS":
            # Wait for the page to finish post-submit redirect/reload
            try:
                self.wait.until(lambda d:
                    "edit.php" not in d.current_url
                    or d.find_elements(By.XPATH, "//div[contains(@class,'alert-success')]")
                )
            except TimeoutException:
                pass
            self._click_continue_if_present()
            errors = self.get_all_errors()
            self.assertEqual(errors, "", f"[{tc}] unexpected errors: {errors}")

            if expected:
                self.open_profile_edit()
                time.sleep(1)
                saved = self.driver.find_element(*self.locator("txt_firstname")).get_attribute("value")
                self.assertEqual(
                    saved, expected,
                    f"[{tc}] saved value mismatch: {saved!r} != {expected!r}",
                )

            self._restore_originals()

        elif kind == "ERROR":
            errors = self.get_all_errors()
            if errors:
                self.assertIn(
                    expected.lower(), errors.lower(),
                    f"[{tc}] expected error '{expected}' not in: {errors!r}",
                )
            else:
                self.assertIn(
                    self.edit_frag, self.driver.current_url,
                    f"[{tc}] should still be on the edit page",
                )
        else:
            self.fail(f"[{tc}] unknown expected_type {kind!r}")


def _make_test(row):
    def t(self):
        self.run_case(row)
    t.__doc__ = f"{row['tc_id']} ({row['expected_type'].upper()})"
    return t


for _r in load_data():
    setattr(TestUpdateProfile, "test_" + _r["tc_id"].replace("-", "_"), _make_test(_r))


if __name__ == "__main__":
    unittest.main(verbosity=2)
