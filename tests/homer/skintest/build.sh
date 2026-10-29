#!/bin/bash
# Homer stream: export build/chars/homer.chr (+ homer_b4.chr), host-check skin.c against the Python mirror,
# build tests/homer/skintest/build/EBOOT.PBP.  Run from anywhere.
set -e
cd "$(dirname "$0")/../../.."
source .venv/bin/activate
python tools/char_export.py > /dev/null
python tools/char_export.py --max-bones 4 --out build/chars/homer_b4.chr > /dev/null
T=$(mktemp -d)
cc -O2 -Wall -DSKIN_HOST -I viewer tests/homer/skintest/host_check.c viewer/skin.c -lm -o "$T/host_check"
"$T/host_check" build/chars/homer.chr > "$T/pal.txt" && python tests/homer/skintest/check_host.py "$T/pal.txt"
rm -rf "$T"
export PSPDEV=$PWD/pspdev PATH=$PWD/pspdev/bin:$PATH
psp-cmake -S tests/homer/skintest -B tests/homer/skintest/build > /dev/null
cmake --build tests/homer/skintest/build > /dev/null
ls -la tests/homer/skintest/build/EBOOT.PBP build/chars/homer.chr build/chars/homer_b4.chr
