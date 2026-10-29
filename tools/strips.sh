#!/bin/bash
# сборка tools/strips (meshoptimizer 1.3, MIT; исходники: $MESHOPT или бэкап ресёрча, в репозиторий не входят): tools/strips.sh
set -e; M=${MESHOPT:-$HOME/_backups/shar-psp-audit-2026-09-27_122213/research-2026-09-27/sources/meshoptimizer/src}; cd "$(dirname "$0")"
O=${STRIPS_OBJ:-/tmp/strips_build}; mkdir -p $O
for s in allocator stripifier vcacheoptimizer; do [ $O/$s.o -nt $M/$s.cpp ] || c++ -O2 -std=c++11 -c $M/$s.cpp -o $O/$s.o; done
cc -O2 -I$M -c strips.c -o $O/strips.o && c++ $O/strips.o $O/allocator.o $O/stripifier.o $O/vcacheoptimizer.o -o strips && echo tools/strips
