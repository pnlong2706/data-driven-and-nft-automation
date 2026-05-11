#!/usr/bin/env bash
# Run all feature suites. One line per feature.
set -u
cd "$(dirname "$0")"
EXITCODE=0

./Feature_002_Login/run.sh || EXITCODE=1

# ./Feature_XXX/run.sh || EXITCODE=1

echo
if [ "$EXITCODE" -eq 0 ]; then
    echo "ALL FEATURES PASSED."
else
    echo "ONE OR MORE FEATURES FAILED."
fi
exit "$EXITCODE"
