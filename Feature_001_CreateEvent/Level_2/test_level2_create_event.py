"""Level 2: fully data-driven create-event tests using elements_config.csv + create_event_data.csv."""
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
from selenium.webdriver.support.ui import Select, WebDriverWait

USERNAME = os.getenv("MOODLE_USERNAME", "student")
PASSWORD = os.getenv("MOODLE_PASSWORD", "moodle26")
TIMEOUT = 20

HERE = os.path.dirname(os.path.abspath(__file__))
ELEMENTS_FILE = os.path.join(HERE, "elements_config.csv")
DATA_FILE = os.path.join(HERE, "create_event_data.csv")

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


def read_data():
    return [row for row in load_csv(DATA_FILE) if row.get("testcase")]


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


def is_yes(value):
    return (value or "").strip().upper() == "Y"


def xpath_literal(value):
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ', \'"\', '.join(f'"{p}"' for p in parts) + ")"


class TestCreateEvent(unittest.TestCase):

    elements = load_elements()

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.wait = WebDriverWait(cls.driver, TIMEOUT)
        cls.base_url = cls.elements["base_url"]["value"].rstrip("/")
        cls.login_url = cls.elements["login_url"]["value"]
        cls.calendar_month_url_template = cls.elements["calendar_month_url_template"]["value"]

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def locator(self, name):
        e = self.elements[name]
        return BY_MAP[e["type"]], e["value"]

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

    def _is_login_page(self):
        if "/login/index.php" in self.driver.current_url:
            return True
        if self.driver.find_elements(*self.locator("txt_username")):
            return True
        if self.driver.find_elements(*self.locator("lbl_guest_access")):
            return True
        return bool(self.driver.find_elements(*self.locator("lnk_login")))

    def _login(self):
        for attempt in range(2):
            self.driver.get(self.login_url)
            self.wait.until(EC.presence_of_element_located(self.locator("txt_username")))
            self.type_into("txt_username", USERNAME)
            self.type_into("txt_password", PASSWORD)
            self.driver.find_element(*self.locator("btn_login")).click()
            try:
                self.wait.until(lambda d: "/login/index.php" not in d.current_url)
                return
            except TimeoutException:
                if attempt == 0:
                    continue
                errors = self.driver.find_elements(*self.locator("lbl_login_error"))
                if errors:
                    msg = errors[0].text.strip()
                    self.fail(f"Login failed for user '{USERNAME}': {msg}")
                self.fail(f"Login did not complete for user '{USERNAME}' at {self.base_url}")

    def open_month(self, month_timestamp):
        url = self.calendar_month_url_template.format(month_timestamp)
        try:
            self.driver.get(url)
        except TimeoutException:
            pass
        if self._is_login_page():
            self._login()
            self.driver.get(url)
        self.wait.until(EC.presence_of_element_located(self.locator("btn_new_event")))

    def _select(self, locator, value):
        Select(self.driver.find_element(*locator)).select_by_visible_text(str(value))

    def _fill_event_form(self, row):
        self.wait.until(EC.element_to_be_clickable(self.locator("btn_new_event"))).click()
        self.wait.until(EC.visibility_of_element_located(self.locator("txt_event_name"))).clear()
        self.driver.find_element(*self.locator("txt_event_name")).send_keys(row["event_name"])

        self._select(self.locator("ddl_start_day"), row["start_day"])
        self._select(self.locator("ddl_start_month"), row["start_month"])
        self._select(self.locator("ddl_start_year"), row["start_year"])
        self._select(self.locator("ddl_start_hour"), row["start_hour"])
        self._select(self.locator("ddl_start_minute"), row["start_minute"])

        if is_yes(row.get("use_duration")):
            self.driver.find_element(*self.locator("rdo_enable_duration")).click()
            duration = self.driver.find_element(*self.locator("txt_duration_minutes"))
            duration.clear()
            duration.send_keys(row.get("duration_minutes", ""))

        if is_yes(row.get("use_repeat")):
            repeat_candidates = self.driver.find_elements(*self.locator("chk_repeat"))
            repeat_hidden = bool(repeat_candidates) and not repeat_candidates[0].is_displayed()
            if not repeat_candidates or repeat_hidden:
                show_more = self.driver.find_elements(*self.locator("lnk_show_more"))
                if show_more:
                    show_more[0].click()
            repeat_checkbox = self.wait.until(EC.visibility_of_element_located(self.locator("chk_repeat")))
            if not repeat_checkbox.is_selected():
                repeat_checkbox.click()
            repeats = self.wait.until(EC.visibility_of_element_located(self.locator("txt_repeats")))
            repeats.clear()
            repeats.send_keys(row.get("repeats", ""))

        self.driver.find_element(*self.locator("btn_save_event")).click()

    def _assert_event_visible(self, row):
        self.open_month(row["month_timestamp"])
        event_name = xpath_literal(row["event_name"])
        event_cell_xpath = (
            "//td[contains(@data-day-timestamp,'{day_ts}') and "
            ".//*[contains(normalize-space(.), {event_name})]]"
        ).format(
            day_ts=row["expected_timestamp"],
            event_name=event_name,
        )
        self.wait.until(EC.visibility_of_element_located((By.XPATH, event_cell_xpath)))

    def run_case(self, row):
        self.open_month(row["month_timestamp"])
        self._fill_event_form(row)
        self._assert_event_visible(row)


def make_test(row):
    def t(self):
        self.run_case(row)
    t.__doc__ = row["testcase"]
    return t


for r in read_data():
    setattr(
        TestCreateEvent,
        "test_" + r["testcase"].replace("-", "_"),
        make_test(r),
    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
