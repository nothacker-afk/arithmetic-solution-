#!/bin/bash
# Run the full test suite + optional per-subproject smoke tests.
set -e
cd "$(dirname "$0")/../.."

echo "▶ Full pytest suite"
pytest -q

echo ""
echo "▶ Import smoke tests"
python -c "import arithmetic; print('  arithmetic:', arithmetic.__version__)"
python -c "import ai_engine; print('  ai_engine: ok')"
python -c "import cli; print('  cli: ok')"
python -c "import web.backend.main; print('  web.backend: ok')"
python -c "import arith; print('  arith:', arith.__version__)"
echo ""
echo "✅ All good"
