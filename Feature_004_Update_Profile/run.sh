#!/usr/bin/env bash
# Run all Feature 004 (Update Profile) automation suites.
# Usage:  ./run.sh            # runs all three suites
#         ./run.sh level1     # runs only Level 1
#         ./run.sh level2     # runs only Level 2
#         ./run.sh nf         # runs only Non-Functional
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

run_level1() {
    echo
    echo "========================================================"
    echo " Level 1 - Data-Driven (hard-coded locators)"
    echo "========================================================"
    "$PYTHON" -m unittest Level_1.test_level1_update_profile -v || EXITCODE=1
}

run_level2() {
    echo
    echo "========================================================"
    echo " Level 2 - Fully Data-Driven (config-driven locators)"
    echo "========================================================"
    "$PYTHON" -m unittest Level_2.test_level2_update_profile -v || EXITCODE=1
}

run_nf() {
    echo
    echo "========================================================"
    echo " Non-Functional - Security and Performance"
    echo "========================================================"
    "$PYTHON" -m unittest Non_Functional.test_non_functional_update_profile -v || EXITCODE=1
}

case "$TARGET" in
    all)    run_level1; run_level2; run_nf ;;
    level1) run_level1 ;;
    level2) run_level2 ;;
    nf)     run_nf ;;
    *)      echo "Usage: $0 [all|level1|level2|nf]"; exit 1 ;;
esac

echo
if [ "$EXITCODE" -eq 0 ]; then
    echo "ALL SUITES PASSED."
else
    echo "ONE OR MORE SUITES FAILED."
fi
exit $EXITCODE
