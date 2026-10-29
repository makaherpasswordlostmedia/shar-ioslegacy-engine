#!/bin/sh
# Resume the latest saved campaign; no AI calls, no boot-time service.
set -e
cd "$(dirname "$0")/../.."
if [ -f build/sandbox/soak-current.json ]; then
  exec python3 tools/cartest/sandbox_batch.py --resume-latest --soak-minutes 75
fi
exec python3 tools/cartest/sandbox_batch.py --soak-minutes 75 --workers 6 --seconds 600 --cars 256 --seed 10000
