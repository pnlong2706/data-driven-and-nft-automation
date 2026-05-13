#!/usr/bin/env bash
# Run all Feature 003 (Change Password) automation suites.
# Usage:  ./run.sh            # setup + all three suites
#         ./run.sh level1     # setup + only Level 1
#         ./run.sh level2     # setup + only Level 2
#         ./run.sh nf         # setup + only Non-Functional
set -u

cd "$(dirname "$0")"

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

run_setup() {
    echo
    echo "========================================================"
    echo " Setup - Ensure test account is ready"
    echo "========================================================"
    "$PYTHON" -m unittest setup_feature003.SetupFeature003 -v
}

run_level1() {
    echo
    echo "========================================================"
    echo " Level 1 - Data-Driven (hard-coded locators)"
    echo "========================================================"
    "$PYTHON" -m unittest Level_1.test_level1_change_password -v || EXITCODE=1
}

run_level2() {
    echo
    echo "========================================================"
    echo " Level 2 - Fully Data-Driven (config-driven locators)"
    echo "========================================================"
    "$PYTHON" -m unittest Level_2.test_level2_change_password -v || EXITCODE=1
}

run_nf() {
    echo
    echo "========================================================"
    echo " Non-Functional - Usability and Compatibility"
    echo "========================================================"
    "$PYTHON" -m unittest Non_Functional.test_non_functional_change_password -v || EXITCODE=1
}

# Run setup first; abort the entire run if it fails
if ! run_setup; then
    echo
    echo "Setup failed. Aborting test run."
    exit 1
fi

case "$TARGET" in
    level1)              run_level1 ;;
    level2)              run_level2 ;;
    nf|non_functional)   run_nf ;;
    all|"")              run_level1; run_level2; run_nf ;;
    *) echo "Unknown target: $TARGET (expected: level1 | level2 | nf | all)" >&2; exit 2 ;;
esac

echo
if [ "$EXITCODE" -eq 0 ]; then
    echo "ALL SUITES PASSED."
else
    echo "ONE OR MORE SUITES FAILED."
fi
exit "$EXITCODE"
