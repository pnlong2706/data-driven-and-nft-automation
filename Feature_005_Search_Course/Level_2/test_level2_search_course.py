"""Level 2: fully data-driven search-course tests. URLs and locators from elements_config.csv."""
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
DATA_FILE = os.path.join(HERE, "search_data.csv")

BY_MAP = {
    "ID": By.ID,
    "NAME": By.NAME,
    "XPATH": By.XPATH,
    "CSS": By.CSS_SELECTOR,
    "CLASS": By.CLASS_NAME,
}

CREDENTIALS = ("student", "moodle26")

TWO_HUNDRED_CHARS = "A" * 200


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
    rows = []
    for r in load_csv(DATA_FILE):
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
    opts.page_load_strategy = "eager"
    return webdriver.Chrome(options=opts)


class TestSearchCourse(unittest.TestCase):

    elements = load_elements()

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.driver.set_page_load_timeout(60)
        cls.wait = WebDriverWait(cls.driver, 30)
        cls.site_url = cls.elements["site_url"]["value"]
        cls.success_fragment = cls.elements["success_url_fragment"]["value"]
        cls._login()

    @classmethod
    def _login(cls):
        d = cls.driver
        login_url = cls.elements["login_url"]["value"]
        try:
            d.get(login_url)
        except TimeoutException:
            pass
        d.delete_all_cookies()
        try:
            d.get(login_url)
        except TimeoutException:
            pass
        WebDriverWait(d, 30).until(
            EC.presence_of_element_located(
                (BY_MAP[cls.elements["txt_username"]["type"]],
                 cls.elements["txt_username"]["value"])
            )
        )
        d.find_element(
            BY_MAP[cls.elements["txt_username"]["type"]],
            cls.elements["txt_username"]["value"],
        ).send_keys(CREDENTIALS[0])
        d.find_element(
            BY_MAP[cls.elements["txt_password"]["type"]],
            cls.elements["txt_password"]["value"],
        ).send_keys(CREDENTIALS[1])
        d.find_element(
            BY_MAP[cls.elements["btn_login"]["type"]],
            cls.elements["btn_login"]["value"],
        ).click()
        try:
            WebDriverWait(d, 30).until(
                lambda dr: cls.success_fragment in dr.current_url
            )
        except TimeoutException:
            raise RuntimeError("Login failed – cannot proceed with search tests")

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    # ── Helpers ─────────────────────────────────────────────────────────

    def locator(self, name):
        e = self.elements[name]
        return BY_MAP[e["type"]], e["value"]

    def config_value(self, name):
        return self.elements[name]["value"]

    def open_courses_page(self):
        try:
            self.driver.get(self.site_url)
        except TimeoutException:
            pass
        try:
            self.wait.until(
                EC.presence_of_element_located(self.locator("txt_search"))
            )
        except TimeoutException:
            # Session likely expired — re-login
            self._login()
            try:
                self.driver.get(self.site_url)
            except TimeoutException:
                pass
            self.wait.until(
                EC.presence_of_element_located(self.locator("txt_search"))
            )
        # Wait for Moodle JS to bind (Bootstrap dropdowns, auto-search)
        time.sleep(5)

    def _type_into(self, name, text):
        for _ in range(4):
            try:
                el = self.driver.find_element(*self.locator(name))
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el
                )
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

    def _select_sort(self, data_value):
        """Open sort dropdown and click the matching option."""
        css = f'a[data-filter="sort"][data-value="{data_value}"]'
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )
        btn = self.driver.find_element(*self.locator("btn_sort_dropdown"))
        self.driver.execute_script("arguments[0].click();", btn)
        time.sleep(0.5)
        items = self.driver.find_elements(By.CSS_SELECTOR, css)
        if items:
            self.driver.execute_script("arguments[0].click();", items[0])
        else:
            raise NoSuchElementException(f"Sort option data-value={data_value!r} not found")
        time.sleep(0.5)

    def _select_display(self, data_value):
        """Open display dropdown and click the matching option."""
        css = f'a[data-display-option="display"][data-value="{data_value}"]'
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )
        btn = self.driver.find_element(*self.locator("btn_display_dropdown"))
        self.driver.execute_script("arguments[0].click();", btn)
        time.sleep(0.5)
        items = self.driver.find_elements(By.CSS_SELECTOR, css)
        if items:
            self.driver.execute_script("arguments[0].click();", items[0])
        else:
            raise NoSuchElementException(f"Display option data-value={data_value!r} not found")
        time.sleep(0.5)

    def _wait_for_search_results(self, timeout=15):
        end = time.time() + timeout
        no_courses_text = self.config_value("no_courses_text")
        while time.time() < end:
            has_cards = len(
                self.driver.find_elements(*self.locator("course_info_container"))
            ) > 0
            has_no_courses = no_courses_text in (
                self.driver.find_element(By.TAG_NAME, "body").text
            )
            if has_cards or has_no_courses:
                return
            time.sleep(0.5)

    def _has_course_results(self):
        return len(self.driver.find_elements(*self.locator("course_info_container"))) > 0

    def _has_no_results_message(self):
        no_courses_text = self.config_value("no_courses_text")
        return no_courses_text in self.driver.find_element(By.TAG_NAME, "body").text

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

        sort_label = row.get("sort_by", "Course name")
        sort_val = self.SORT_MAP.get(sort_label, "fullname")
        self._select_sort(sort_val)

        display_label = row.get("display_mode", "Card")
        display_val = self.DISPLAY_MAP.get(display_label, "card")
        self._select_display(display_val)

        search_text = row.get("search_text", "")
        self._type_into("txt_search", search_text)

        # Give the auto-search time to trigger and the DOM to update
        time.sleep(3)

        self._wait_for_search_results()

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


for r in load_data():
    setattr(
        TestSearchCourse,
        "test_" + r["tc_id"].replace("-", "_"),
        make_test(r),
    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
