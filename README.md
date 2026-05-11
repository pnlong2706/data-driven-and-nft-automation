# Moodle Automation Tests

Selenium tests for the Mount Orange Moodle demo (https://school.moodledemo.net).
Each feature has its own folder with Level 1, Level 2 and Non_Functional suites.

## Layout

```
.
├── Feature_002_Login/
│   ├── Level_1/           # data-driven, hard-coded locators
│   ├── Level_2/           # fully data-driven, locators from CSV
│   ├── Non_Functional/    # brute-force + response time
│   ├── run.bat
│   └── run.sh
├── requirements.txt
├── run.bat                # runs every feature
└── run.sh                 # same, for bash
```

More features (Feature_003_..., etc.) will be added later. Each new feature
should have its own `run.bat` / `run.sh` and one extra line in the outer
`run.bat` / `run.sh`.

## Requirements

- Python 3.10+
- Chrome installed (Selenium Manager fetches the matching chromedriver)
- Internet access (tests hit the live demo site)

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On bash / Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

All features at once:

```powershell
.\run.bat
```

```bash
./run.sh
```

Just one feature:

```powershell
cd Feature_002_Login
.\run.bat               # all three suites for this feature
.\run.bat level1        # only Level 1
.\run.bat level2        # only Level 2
.\run.bat nf            # only Non-Functional
```

Same args work for `run.sh`.

## Notes

- Tests use Chrome in headless mode. To watch them run, remove the
  `--headless=new` line in the `make_driver()` of each test file.
- The Non-Functional performance budget is set to 8s (the live demo over the
  public internet routinely measures 4-10s). Tighten to 3s for an on-prem
  / staging environment.
- All login data and expected results live in CSV files next to each test,
  so adding cases doesn't need code changes for Level 1 / Level 2.
