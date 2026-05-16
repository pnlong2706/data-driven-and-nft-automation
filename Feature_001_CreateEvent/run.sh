#!/usr/bin/env bash
# Run all Feature 001 (Create Event) automation suites.
# Usage:  ./run.sh            # runs all suites
#         ./run.sh level1     # runs only Level 1
#         ./run.sh level2     # runs only Level 2
#         ./run.sh nf         # runs only Non-Functional
# Optional env for login/setup:
#         MOODLE_BASE_URL=https://school.moodledemo.net
#         MOODLE_USERNAME=student
#         MOODLE_PASSWORD=moodle26
set -u

cd "$(dirname "$0")"

# Locate the Python interpreter: prefer the venv at ../.venv (Windows / *nix layouts), fall back to system python.
PYTHON=""
for candidate in "../.venv/Scripts/python.exe" "../.venv/bin/python" "python3" "python"; do
    if command -v "$candidate" >/dev/null 2>&1 || [ -x "$candidate" ]; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: could not find a Python interpreter." >&2
    exit 127
fi

TARGET="${1:-all}"
EXITCODE=0

run_level1() {
    echo
    echo "========================================================"
    echo " Level 1 - Data-Driven (hard-coded locators)"
    echo "========================================================"
    "$PYTHON" -m unittest Level_1.test_level1_create_event -v || EXITCODE=1
}

run_level2() {
    echo
    echo "========================================================"
    echo " Level 2 - Fully Data-Driven (config-driven locators)"
    echo "========================================================"
    "$PYTHON" -m unittest Level_2.test_level2_create_event -v || EXITCODE=1
}

run_nf() {
    echo
    echo "========================================================"
    echo " Non-Functional - Security and Performance"
    echo "========================================================"
    "$PYTHON" -m unittest Non_Functional.test_non_functional_create_event -v || EXITCODE=1
}

case "$TARGET" in
    level1)         run_level1 ;;
    level2)         run_level2 ;;
    nf|non_functional) run_nf ;;
    all|"")         run_level1; run_level2; run_nf ;;
    *) echo "Unknown target: $TARGET (expected: level1 | level2 | nf | all)" >&2; exit 2 ;;
esac

echo
if [ "$EXITCODE" -eq 0 ]; then
    echo "ALL SUITES PASSED."
else
    echo "ONE OR MORE SUITES FAILED."
fi
exit "$EXITCODE"
