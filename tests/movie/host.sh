#!/bin/bash
# Разбор SMV1 на Маке тем же кодом, что на PSP (tests/movie/host.c), с AddressSanitizer/UBSan.
#   tests/movie/host.sh [FILE.smv...]   по умолчанию build/movies/*.smv
set -e; cd "$(dirname "$0")/../.."
cc -std=c99 -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all -Wall -I viewer tests/movie/host.c -o build/movie-host
if [ $# -eq 0 ]; then set -- build/movies/vuglogo.smv build/movies/foxlogo.smv build/movies/gracie.smv build/movies/radlogo.smv build/movies/intro.smv; fi
build/movie-host "$@"
