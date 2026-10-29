#!/bin/bash
# Бот пешком по настоящей коллизии (разбор ночи 02.10 для приёмки L1, 03.10): прямая к цели перекрыта — путь A* по сетке 0.5 м
# (tools/bots/footpath.h, missioner.c). Случаи из ночи: m0 — своя машина встала у двери Kwik-E-Mart, Гомер упирался в неё;
# m1 — к двери школы прямая упирается в боковую стенку крыльца (z3_schoolShape199), вход по ступеням с востока.
# Проверки в мире EBOOT (build/: уровень, кузова машин миссий, реплики): красный MISSIONER_NO_FOOTGRID=1 — обе миссии «застрял
# пешком»; зелёный — обе «пройдена».
#   tests/bots/footgrid.sh   -> PASS/FAIL; рабочие файлы build/bots/gate_footgrid/
cd "$(dirname "$0")/../.."
O=build/bots/gate_footgrid; rm -rf "$O"; mkdir -p "$O"
BINS=missioner OUT_DIR=$O tools/bots/build.sh >/dev/null || { echo "FAIL: сборка миссионера"; exit 1; }
A="build/level.shr build/homer.shr build/sandbox/roads-l1.bin build/missions/level01.msn"
run() { nice -n 10 $O/missioner $A --mission $1 --secs 900 | grep '^M' | cut -f3,5,6,7; }
echo "== красный: MISSIONER_NO_FOOTGRID=1 (бот пешком только по прямой и шагами вбок)"
R0=$(MISSIONER_NO_FOOTGRID=1 run 0); R1=$(MISSIONER_NO_FOOTGRID=1 run 1); echo "  $R0"; echo "  $R1"
red=0; case "$R0" in *застрял*) red=$((red + 1));; esac; case "$R1" in *застрял*) red=$((red + 1));; esac
echo "== зелёный"
G0=$(run 0); G1=$(run 1); echo "  $G0"; echo "  $G1"
green=1; case "$G0" in *пройдена*) ;; *) green=0;; esac; case "$G1" in *пройдена*) ;; *) green=0;; esac
echo "красных поймано $red из 2"
[ $red = 2 ] && [ $green = 1 ] && echo "PASS" || { echo "FAIL"; exit 1; }
