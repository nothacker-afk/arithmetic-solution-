#!/bin/bash
# Print a workspace health summary.
cd "$(dirname "$0")/../.."

echo "Workspace: $(pwd)"
echo ""
echo "Subprojects:"
for d in arithmetic ai_engine cli web mobile arith alembic k8s helm docker; do
    if [ -d "$d" ]; then
        files=$(find "$d" -type f -not -path '*/__pycache__/*' | wc -l | tr -d ' ')
        printf "  ✅ %-12s %s files\n" "$d" "$files"
    else
        printf "  ❌ %-12s MISSING\n" "$d"
    fi
done
echo ""
echo "Tests:"
if [ -d tests ]; then
    n=$(ls tests/test_*.py 2>/dev/null | wc -l | tr -d ' ')
    echo "  $n test files"
fi
echo ""
echo "Version: $(python -c 'import arithmetic; print(arithmetic.__version__)')"
