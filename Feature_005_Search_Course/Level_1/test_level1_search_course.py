"""Level 1: data-driven search-course tests. Locators hard-coded, data from CSV."""
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

# ── Hard-coded constants ──────────────────────────────────────────────
LOGIN_URL = "https://school.moodledemo.net/login/index.php"
COURSES_URL = "https://school.moodledemo.net/my/courses.php"
SUCCESS_FRAGMENT = "/my/"

USERNAME_ID = "username"
PASSWORD_ID = "password"
LOGIN_BTN_ID = "loginbtn"
LOGIN_ERROR_XPATH = (
    "//*[@id='loginerrormessage' or contains(@class,'loginerrors') "
    "or contains(@class,'alert-danger')]"
)

# Real locators discovered from the live Moodle page:
SEARCH_INPUT_NAME = "search"          # <input name="search"> (ID is dynamic)
SORT_DROPDOWN_ID = "sortingdropdown"  # <button id="sortingdropdown">
DISPLAY_DROPDOWN_ID = "displaydropdown"  # <button id="displaydropdown">
COURSE_INFO_CSS = ".course-info-container"  # course card body
COURSES_VIEW_CSS = "[data-region='courses-view']"  # main container
NO_COURSES_TEXT = "No courses"        # substring in the no-results message

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "search_data.csv")

CREDENTIALS = ("student", "moodle26")

# Placeholder in CSV that means "200-character string"
TWO_HUNDRED_CHARS = "A" * 200


def read_data():
    rows = []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("tc_id"):
                continue
            if r["search_text"] == "{200_CHARS}":
                r["search_text"] = TWO_HUNDRED_CHARS
            rows.append(r)
    return rows


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # "eager" returns as soon as DOM is ready, avoiding 120s timeouts
    # on the heavy Moodle demo site. We then explicitly wait for JS below.
    opts.page_load_strategy = "eager"
    return webdriver.Chrome(options=opts)


class TestSearchCourse(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.driver.set_page_load_timeout(60)
        cls.wait = WebDriverWait(cls.driver, 30)
        cls._login()

    @classmethod
    def _login(cls):
        """Log in once and keep the session for all search tests."""
        d = cls.driver
        try:
            d.get(LOGIN_URL)
        except TimeoutException:
            pass
        d.delete_all_cookies()
        try:
            d.get(LOGIN_URL)
        except TimeoutException:
            pass
        WebDriverWait(d, 30).until(
            EC.presence_of_element_located((By.ID, USERNAME_ID))
        )
        d.find_element(By.ID, USERNAME_ID).send_keys(CREDENTIALS[0])
        d.find_element(By.ID, PASSWORD_ID).send_keys(CREDENTIALS[1])
        d.find_element(By.ID, LOGIN_BTN_ID).click()
        try:
            WebDriverWait(d, 30).until(
                lambda dr: SUCCESS_FRAGMENT in dr.current_url
            )
        except TimeoutException:
            raise RuntimeError("Login failed – cannot proceed with search tests")

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    # ── Page helpers ───────────────────────────────────────────────────

    def open_courses_page(self):
        try:
            self.driver.get(COURSES_URL)
        except TimeoutException:
            pass
        # Check if we landed on the courses page or got redirected to login
        try:
            self.wait.until(
                EC.presence_of_element_located((By.NAME, SEARCH_INPUT_NAME))
            )
        except TimeoutException:
            # Session likely expired — re-login
            self._login()
            try:
                self.driver.get(COURSES_URL)
            except TimeoutException:
                pass
            self.wait.until(
                EC.presence_of_element_located((By.NAME, SEARCH_INPUT_NAME))
            )
        # With "eager" strategy the DOM is ready but Moodle's JS (Bootstrap
        # dropdowns, auto-search) needs more time to bind.
        time.sleep(5)

    def _type_into(self, locator_tuple, text):
        """Type into a field with retry / JS fallback."""
        for _ in range(4):
            try:
                el = self.driver.find_element(*locator_tuple)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el
                )
                el.clear()
                if text:
                    el.send_keys(text)
                return
            except (StaleElementReferenceException, ElementNotInteractableException):
                time.sleep(0.4)
        # JS fallback
        el = self.driver.find_element(*locator_tuple)
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el, text or "",
        )

    def _select_sort(self, data_value):
        """Click a sort option from the Bootstrap dropdown.

        data_value maps to the <a data-filter="sort" data-value="..."> attribute:
          - "fullname"           → Course name
          - "ul.timeaccess desc" → Last accessed
          - "startdate"          → Start date
        """
        css = f'a[data-filter="sort"][data-value="{data_value}"]'
        # Wait for the menu item to exist in the DOM
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )
        # Open the dropdown via JS
        btn = self.driver.find_element(By.ID, SORT_DROPDOWN_ID)
        self.driver.execute_script("arguments[0].click();", btn)
        time.sleep(0.5)
        # Click the matching menu item via JS (doesn't need to be visible)
        items = self.driver.find_elements(By.CSS_SELECTOR, css)
        if items:
            self.driver.execute_script("arguments[0].click();", items[0])
        else:
            raise NoSuchElementException(
                f"Sort option data-value={data_value!r} not found"
            )
        time.sleep(0.5)

    def _select_display(self, data_value):
        """Click a display option from the Bootstrap dropdown.

        data_value maps to the <a data-display-option="display" data-value="..."> attribute:
          - "card"    → Card view
          - "list"    → List view
          - "summary" → Summary view
        """
        css = f'a[data-display-option="display"][data-value="{data_value}"]'
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )
        btn = self.driver.find_element(By.ID, DISPLAY_DROPDOWN_ID)
        self.driver.execute_script("arguments[0].click();", btn)
        time.sleep(0.5)
        items = self.driver.find_elements(By.CSS_SELECTOR, css)
        if items:
            self.driver.execute_script("arguments[0].click();", items[0])
        else:
            raise NoSuchElementException(
                f"Display option data-value={data_value!r} not found"
            )
        time.sleep(0.5)

    def _wait_for_search_results(self, timeout=20):
        """Wait until either course content appears or the 'no courses' message shows."""
        end = time.time() + timeout
        while time.time() < end:
            if self._has_course_results() or self._has_no_results_message():
                return
            time.sleep(0.5)

    def _has_course_results(self):
        """Check for course content using multiple selectors that work across all views."""
        # .course-info-container works for Card view
        if len(self.driver.find_elements(By.CSS_SELECTOR, COURSE_INFO_CSS)) > 0:
            return True
        # Broader: any element with data-region containing "course" and "content"
        if len(self.driver.find_elements(
            By.CSS_SELECTOR, "[data-region='course-view-content']"
        )) > 0:
            return True
        # Fallback: check if the courses-view container has child elements
        # (not just the empty/skeleton state)
        containers = self.driver.find_elements(
            By.CSS_SELECTOR, "[data-region='courses-view']"
        )
        for c in containers:
            # If the container has real content (not just loading skeletons)
            inner = c.find_elements(By.CSS_SELECTOR, "a[href*='course'], .course-card, .course-info-container, .course-summaryitem, .list-group-item")
            if inner:
                return True
        return False

    def _has_no_results_message(self):
        """Check for the 'No courses' message in multiple ways."""
        body_text = self.driver.find_element(By.TAG_NAME, "body").text
        if NO_COURSES_TEXT in body_text:
            return True
        # Also check for the specific no-results element
        no_result_els = self.driver.find_elements(
            By.CSS_SELECTOR, "[data-region='empty-message'], .nocourses, .no-results"
        )
        for el in no_result_els:
            if el.is_displayed():
                return True
        return False

    # ── Sort/display value mapping ─────────────────────────────────────

    SORT_MAP = {
        "Course name": "fullname",
        "Last accessed": "ul.timeaccess desc",
        "Start date": "startdate",
    }

    DISPLAY_MAP = {
        "Card": "card",
        "Summary": "summary",
        "List": "list",
    }

    # ── Test runner ────────────────────────────────────────────────────

    def run_case(self, row):
        tc = row["tc_id"]
        self.open_courses_page()

        # 1. Set sort-by dropdown
        sort_label = row.get("sort_by", "Course name")
        sort_val = self.SORT_MAP.get(sort_label, "fullname")
        self._select_sort(sort_val)

        # 2. Set display-mode dropdown
        display_label = row.get("display_mode", "Card")
        display_val = self.DISPLAY_MAP.get(display_label, "card")
        self._select_display(display_val)

        # 3. Type search text (auto-search triggers)
        search_text = row.get("search_text", "")
        self._type_into((By.NAME, SEARCH_INPUT_NAME), search_text)

        # 4. Give the auto-search time to trigger and the DOM to update.
        #    Without this delay, stale course cards from the previous state
        #    may still be in the DOM, causing false positives/negatives.
        time.sleep(3)

        # 5. Wait for results to settle
        self._wait_for_search_results()

        # 5. Assert
        kind = row["expected_type"].upper()
        expected = row["expected_value"]

        if kind == "COURSES":
            self.assertTrue(
                self._has_course_results(),
                f"[{tc}] Expected course results but found none",
            )
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            self.assertIn(
                expected, page_text,
                f"[{tc}] Expected keyword '{expected}' not found on page",
            )

        elif kind == "NO_RESULTS":
            self.assertTrue(
                self._has_no_results_message(),
                f"[{tc}] Expected 'No courses' message but it was not visible",
            )

        elif kind == "ALL_COURSES":
            self.assertFalse(
                self._has_no_results_message(),
                f"[{tc}] Empty search should show all courses, not 'no results'",
            )
            self.assertTrue(
                self._has_course_results(),
                f"[{tc}] Empty search should show all courses",
            )

        else:
            self.fail(f"[{tc}] Unknown expected_type: {kind!r}")


def make_test(row):
    def t(self):
        self.run_case(row)
    t.__doc__ = f"{row['tc_id']} ({row['expected_type'].upper()})"
    return t


for r in read_data():
    setattr(
        TestSearchCourse,
        "test_" + r["tc_id"].replace("-", "_"),
        make_test(r),
    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
