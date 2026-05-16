"""Level 1: data-driven create-event tests. Locators hard-coded, data from CSV."""
import csv
import os
import unittest

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

BASE_URL = os.getenv("MOODLE_BASE_URL", "https://school.moodledemo.net").rstrip("/")
LOGIN_URL = f"{BASE_URL}/login/index.php"
CALENDAR_MONTH_URL = f"{BASE_URL}/calendar/view.php?view=month&time={{}}"

USERNAME = os.getenv("MOODLE_USERNAME", "student")
PASSWORD = os.getenv("MOODLE_PASSWORD", "moodle26")
TIMEOUT = 20

LOC_USERNAME = (By.ID, "username")
LOC_PASSWORD = (By.ID, "password")
LOC_LOGIN_BTN = (By.ID, "loginbtn")
LOC_LOGIN_ERROR = (
    By.XPATH,
    "//*[@id='loginerrormessage' or contains(@class,'loginerrors') or contains(@class,'alert-danger')]",
)
LOC_GUEST_ACCESS = (By.XPATH, "//*[contains(normalize-space(.), 'guest access')]")
LOC_LOGIN_LINK = (
    By.XPATH,
    "//a[contains(@href, '/login/index.php')][contains(normalize-space(.), 'Log in')]",
)

LOC_NEW_EVENT_BTN = (By.XPATH, "//button[contains(@data-action,'new-event-button')]")
LOC_EVENT_NAME = (By.ID, "id_name")
LOC_START_DAY = (By.ID, "id_timestart_day")
LOC_START_MONTH = (By.ID, "id_timestart_month")
LOC_START_YEAR = (By.ID, "id_timestart_year")
LOC_START_HOUR = (By.ID, "id_timestart_hour")
LOC_START_MINUTE = (By.ID, "id_timestart_minute")
LOC_ENABLE_DURATION = (By.ID, "id_duration_2")
LOC_DURATION_MINUTES = (By.ID, "id_timedurationminutes")
LOC_SHOW_MORE = (By.CSS_SELECTOR, "a.moreless-toggler")
LOC_REPEAT_CHECKBOX = (By.ID, "id_repeat")
LOC_REPEATS = (By.ID, "id_repeats")
LOC_SAVE_BTN = (By.XPATH, "//button[contains(@data-action,'save')]")


def _find_data_file():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "create_event_data.csv"),
        os.path.join(os.path.dirname(here), "create_event_data.csv"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("create_event_data.csv not found in Level_1 or feature root")


DATA_FILE = _find_data_file()


def read_data():
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if row.get("testcase")]


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

    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        cls.wait = WebDriverWait(cls.driver, TIMEOUT)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def _is_login_page(self):
        if "/login/index.php" in self.driver.current_url:
            return True
        if self.driver.find_elements(*LOC_USERNAME):
            return True
        if self.driver.find_elements(*LOC_GUEST_ACCESS):
            return True
        return bool(self.driver.find_elements(*LOC_LOGIN_LINK))

    def _login(self):
        for attempt in range(2):
            self.driver.get(LOGIN_URL)
            self.wait.until(EC.presence_of_element_located(LOC_USERNAME)).clear()
            self.driver.find_element(*LOC_USERNAME).send_keys(USERNAME)
            self.driver.find_element(*LOC_PASSWORD).clear()
            self.driver.find_element(*LOC_PASSWORD).send_keys(PASSWORD)
            self.driver.find_element(*LOC_LOGIN_BTN).click()
            try:
                self.wait.until(lambda d: "/login/index.php" not in d.current_url)
                return
            except TimeoutException:
                if attempt == 0:
                    continue
                errors = self.driver.find_elements(*LOC_LOGIN_ERROR)
                if errors:
                    msg = errors[0].text.strip()
                    self.fail(f"Login failed for user '{USERNAME}': {msg}")
                self.fail(f"Login did not complete for user '{USERNAME}' at {BASE_URL}")

    def open_month(self, month_timestamp):
        url = CALENDAR_MONTH_URL.format(month_timestamp)
        try:
            self.driver.get(url)
        except TimeoutException:
            pass
        if self._is_login_page():
            self._login()
            self.driver.get(url)
        self.wait.until(EC.presence_of_element_located(LOC_NEW_EVENT_BTN))

    def _select(self, locator, value):
        Select(self.driver.find_element(*locator)).select_by_visible_text(str(value))

    def _fill_event_form(self, row):
        self.wait.until(EC.element_to_be_clickable(LOC_NEW_EVENT_BTN)).click()
        self.wait.until(EC.visibility_of_element_located(LOC_EVENT_NAME)).clear()
        self.driver.find_element(*LOC_EVENT_NAME).send_keys(row["event_name"])

        self._select(LOC_START_DAY, row["start_day"])
        self._select(LOC_START_MONTH, row["start_month"])
        self._select(LOC_START_YEAR, row["start_year"])
        self._select(LOC_START_HOUR, row["start_hour"])
        self._select(LOC_START_MINUTE, row["start_minute"])

        if is_yes(row.get("use_duration")):
            self.driver.find_element(*LOC_ENABLE_DURATION).click()
            duration = self.driver.find_element(*LOC_DURATION_MINUTES)
            duration.clear()
            duration.send_keys(row.get("duration_minutes", ""))

        if is_yes(row.get("use_repeat")):
            repeat_candidates = self.driver.find_elements(*LOC_REPEAT_CHECKBOX)
            repeat_hidden = bool(repeat_candidates) and not repeat_candidates[0].is_displayed()
            if not repeat_candidates or repeat_hidden:
                show_more = self.driver.find_elements(*LOC_SHOW_MORE)
                if show_more:
                    show_more[0].click()
            repeat_checkbox = self.wait.until(EC.visibility_of_element_located(LOC_REPEAT_CHECKBOX))
            if not repeat_checkbox.is_selected():
                repeat_checkbox.click()
            repeats = self.wait.until(EC.visibility_of_element_located(LOC_REPEATS))
            repeats.clear()
            repeats.send_keys(row.get("repeats", ""))

        self.driver.find_element(*LOC_SAVE_BTN).click()

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
