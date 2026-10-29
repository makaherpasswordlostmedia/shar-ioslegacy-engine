#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
exec python3 tools/ps2ref/profile.py stop
