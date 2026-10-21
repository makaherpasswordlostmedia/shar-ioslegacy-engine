#!/bin/sh
# Double-click on macOS. No AI calls or downloaded packages.
set -e
cd "$(dirname "$0")/../.."
mkdir -p build/sandbox
if [ ! -f build/sandbox/roads-l1.bin ]; then
  .venv/bin/python tools/cartest/roads.py --level 1 --out build/sandbox/roads-l1.bin
fi
exec python3 tools/cartest/sandbox.py --level build/level.shr --roads build/sandbox/roads-l1.bin --cars 1024 --port 8794 --reuse --open
