#!/bin/bash
# сборка strip_probe (meshoptimizer 1.3, MIT, исходники из бэкапа ресёрча; в репозиторий не входят): tools/strip_probe.sh [out_dir]
set -e; M=${MESHOPT:-$HOME/_backups/shar-psp-audit-2026-09-27_122213/research-2026-09-27/sources/meshoptimizer/src}; O=${1:-/tmp/strip_probe_build}; mkdir -p $O
cd "$(dirname "$0")"
for s in allocator stripifier vcacheoptimizer; do c++ -O2 -std=c++11 -c $M/$s.cpp -o $O/$s.o; done
cc -O2 -I$M -c strip_probe.c -o $O/sp.o && c++ $O/sp.o $O/allocator.o $O/stripifier.o $O/vcacheoptimizer.o -o $O/strip_probe && echo $O/strip_probe
