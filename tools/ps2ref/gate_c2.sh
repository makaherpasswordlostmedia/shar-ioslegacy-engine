#!/bin/bash
# Н2.1: explicit nonzero exit, no personal emulator access
set -euo pipefail
cd "$(dirname "$0")/../.."
exec python3 tools/ps2ref/gate_c2.py "$@"
