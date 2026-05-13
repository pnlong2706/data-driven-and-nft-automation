# -*- coding: utf-8 -*-
"""
Idempotent setup: creates the 'test_password_change' user on school.moodledemo.net
and accepts the site-policy wizard on its behalf.

Called automatically by run.bat / run.sh before the test suites.
Checks account state first so it is safe to run multiple times:

  'ready'        - account exists and policy accepted  → skip everything
  'needs_policy' - account exists, policy not accepted → accept policy only
  'missing'      - account does not exist              → full setup
"""
import unittest

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    NoAlertPresentException,
    StaleElementReferenceException,
    TimeoutException,
)

LOGIN_URL    = "https://school.moodledemo.net/login/index.php"
NEW_USER_URL = "https://school.moodledemo.net/user/editadvanced.php?id=-1"

MANAGER_USER   = "manager"
MANAGER_PASS   = "moodle26"

TEST_USERNAME  = "test_password_change"
TEST_PASSWORD  = "moodle26"
TEST_FIRSTNAME = "Nhi"
TEST_LASTNAME  = "Nguyen"
TEST_EMAIL     = "example@gmail.com"

LOC_USERNAME      = (By.ID,        "username")
LOC_PASSWORD      = (By.ID,        "password")
LOC_LOGIN_BTN     = (By.ID,        "loginbtn")
LOC_USER_MENU     = (By.ID,        "user-menu-toggle")
LOC_LOGOUT_LINK   = (By.LINK_TEXT, "Log out")

LOC_NEW_USERNAME  = (By.ID,        "id_username")
LOC_NEW_FIRSTNAME = (By.ID,        "id_firstname")
LOC_NEW_LASTNAME  = (By.ID,        "id_lastname")
LOC_NEW_EMAIL     = (By.ID,        "id_email")
LOC_NEW_PASSWORD  = (By.ID,        "id_newpassword")
LOC_SUBMIT_BTN    = (By.ID,        "id_submitbutton")

LOC_NEXT_LINK     = (By.LINK_TEXT, "Next")
LOC_POLICY_CB_8   = (By.NAME,      "status8")
LOC_POLICY_CB_12  = (By.NAME,      "status12")
LOC_POLICY_CB_13  = (By.NAME,      "status13")
LOC_POLICY_SUBMIT = (By.NAME,      "submit")

TIMEOUT = 20


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


class SetupFeature003(unittest.TestCase):

    def setUp(self):
        self.driver = make_driver()
        self.driver.implicitly_wait(30)
        self.verificationErrors = []

    def test_setup_feature003(self):
        driver = self.driver
        wait   = WebDriverWait(driver, TIMEOUT,
                               ignored_exceptions=[StaleElementReferenceException])

        status = self._check_account_status()
        print(f"\n[Setup] Account status: {status}")

        if status == "ready":
            print("[Setup] Account already set up. Nothing to do.")
            return

        if status == "missing":
            # Full setup: create the account then fall through to accept policy
            self._login_as_manager(driver, wait)
            self._create_test_user(driver, wait)
            self._logout(driver, wait)
            self._login_as_test_user(driver, wait)
        # 'needs_policy': browser is already on the policy wizard -> fall through

        self._accept_policy(driver, wait)
        self._logout(driver, wait)

    # account-state detection 

    def _check_account_status(self):
        """
        Attempt to log in as the test account.

        Returns:
          'ready'        - reached the dashboard (user menu visible)
          'needs_policy' - redirected to the site-policy wizard (Next link visible)
          'missing'      - login was rejected (neither element appeared)

        Side-effects:
          'ready'        -> logs out before returning (browser back at login page)
          'needs_policy' -> leaves browser logged in on the policy wizard
        """
        driver = self.driver
        wait   = WebDriverWait(driver, TIMEOUT,
                               ignored_exceptions=[StaleElementReferenceException])

        driver.get(LOGIN_URL)
        driver.find_element(*LOC_USERNAME).clear()
        driver.find_element(*LOC_USERNAME).send_keys(TEST_USERNAME)
        driver.find_element(*LOC_PASSWORD).clear()
        driver.find_element(*LOC_PASSWORD).send_keys(TEST_PASSWORD)
        driver.find_element(*LOC_LOGIN_BTN).click()

        try:
            # Wait for the first sign of a successful login
            WebDriverWait(driver, 15).until(EC.any_of(
                EC.presence_of_element_located(LOC_USER_MENU),
                EC.presence_of_element_located(LOC_NEXT_LINK),
            ))
        except TimeoutException:
            return "missing"

        try:
            driver.find_element(*LOC_USER_MENU)
            # Dashboard reached – policy already accepted
            self._logout(driver, wait)
            return "ready"
        except NoSuchElementException:
            # Policy wizard appeared – leave browser here for _accept_policy
            return "needs_policy"

    # setup steps

    def _login_as_manager(self, driver, wait):
        driver.get(LOGIN_URL)
        driver.find_element(*LOC_USERNAME).clear()
        driver.find_element(*LOC_USERNAME).send_keys(MANAGER_USER)
        driver.find_element(*LOC_PASSWORD).clear()
        driver.find_element(*LOC_PASSWORD).send_keys(MANAGER_PASS)
        driver.find_element(*LOC_LOGIN_BTN).click()
        wait.until(EC.presence_of_element_located(LOC_USER_MENU))

    def _create_test_user(self, driver, wait):
        driver.get(NEW_USER_URL)
        driver.find_element(*LOC_NEW_USERNAME).clear()
        driver.find_element(*LOC_NEW_USERNAME).send_keys(TEST_USERNAME)
        driver.find_element(*LOC_NEW_FIRSTNAME).clear()
        driver.find_element(*LOC_NEW_FIRSTNAME).send_keys(TEST_FIRSTNAME)
        driver.find_element(*LOC_NEW_LASTNAME).clear()
        driver.find_element(*LOC_NEW_LASTNAME).send_keys(TEST_LASTNAME)
        driver.find_element(*LOC_NEW_EMAIL).clear()
        driver.find_element(*LOC_NEW_EMAIL).send_keys(TEST_EMAIL)
        # Password field may be hidden by Moodle's "generate password" checkbox;
        # set its value via JS so it is submitted regardless of visibility.
        driver.execute_script(
            "document.getElementById(arguments[0]).value = arguments[1];",
            LOC_NEW_PASSWORD[1], TEST_PASSWORD
        )
        driver.find_element(*LOC_SUBMIT_BTN).click()

    def _login_as_test_user(self, driver, wait):
        driver.get(LOGIN_URL)
        # Wait for page to settle, then re-find each element fresh to avoid
        # StaleElementReferenceException caused by Moodle's JS re-rendering the
        # form after the username field is interacted with.
        wait.until(EC.presence_of_element_located(LOC_USERNAME))
        driver.find_element(*LOC_USERNAME).clear()
        driver.find_element(*LOC_USERNAME).send_keys(TEST_USERNAME)
        wait.until(EC.presence_of_element_located(LOC_PASSWORD))
        driver.find_element(*LOC_PASSWORD).clear()
        driver.find_element(*LOC_PASSWORD).send_keys(TEST_PASSWORD)
        wait.until(EC.element_to_be_clickable(LOC_LOGIN_BTN)).click()

    def _accept_policy(self, driver, wait):
        # Navigate through three "Next" pages of the site-policy wizard.
        # JS click bypasses any sticky overlay that intercepts normal clicks.
        for _ in range(3):
            el = wait.until(EC.element_to_be_clickable(LOC_NEXT_LINK))
            driver.execute_script("arguments[0].click();", el)
        # Agree to each required policy checkbox then submit
        for loc in (LOC_POLICY_CB_8, LOC_POLICY_CB_12, LOC_POLICY_CB_13):
            el = wait.until(EC.element_to_be_clickable(loc))
            driver.execute_script("arguments[0].click();", el)
        el = wait.until(EC.element_to_be_clickable(LOC_POLICY_SUBMIT))
        driver.execute_script("arguments[0].click();", el)
        wait.until(EC.presence_of_element_located(LOC_USER_MENU))

    def _logout(self, driver, wait):
        wait.until(EC.element_to_be_clickable(LOC_USER_MENU)).click()
        wait.until(EC.element_to_be_clickable(LOC_LOGOUT_LINK)).click()

    #  unittest compatibility helpers 

    def is_element_present(self, how, what):
        try:
            self.driver.find_element(by=how, value=what)
        except NoSuchElementException:
            return False
        return True

    def is_alert_present(self):
        try:
            self.driver.switch_to.alert
        except NoAlertPresentException:
            return False
        return True

    def tearDown(self):
        self.driver.quit()
        self.assertEqual([], self.verificationErrors)


if __name__ == "__main__":
    unittest.main()
