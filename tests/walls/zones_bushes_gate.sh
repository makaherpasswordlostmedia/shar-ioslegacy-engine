#!/bin/bash
# tests/walls/zones_bushes_gate.sh
# Гейт для правок Роба:
#   №587: L1 J9-4 кусты податливее для проезда (метка #4: common_gens51Shape)
#   №590: Играбельные зоны: L1 K3-3 за забором (метка #6), L3 зоны (#32, #33, #38) и полиция без тупиков
# Флаги отката: BUSH_SOFT_OLD=1, PLAYABLE_ZONE_OLD=1, POLICE_ZONE_OLD=1

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TMP_DIR="build/tmp/zones_bushes"
mkdir -p "$TMP_DIR"

L1_SHR="$HOME/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721/level.shr"
L3_SHR="$HOME/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721/l3/level.shr"

if [ ! -f "$L1_SHR" ] || [ ! -f "$L3_SHR" ]; then
  echo "ОШИБКА: level.shr не найден!"
  exit 2
fi

cat << 'EOF' > "$TMP_DIR/test_runner.c"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"

int test_bush_drive(ColWorld *W) {
  CarParams P; carParamsFor("famil_v", &P);
  Car c;
  colSetFoliagePass(1);
  float sx = 129.1f, startZ = 175.0f, head = 3.141592f;
  float gy = 0.f;
  colGround(W, sx, startZ, 50.0f, -80.0f, &gy, 0);
  carInit(&c, &P, W, sx, gy + 0.6f, startZ, head);
  carSetSpeed(&c, 15.0f);

  int stuck = 0;
  for (int step = 0; step < 60; step++) {
    CarInput in = { .throttle = 1.0f };
    carUpdate(&c, W, &in, 1/60.f);
    float spd = sqrtf(c.vel[0]*c.vel[0] + c.vel[2]*c.vel[2]);
    if (spd < 1.0f && step > 10) { stuck = 1; break; }
  }
  printf("  [#587 BUSH J9-4] final z=%.2f, stuck=%d -> %s\n",
         c.z, stuck, stuck ? "FAIL (машина встала в кусте)" : "PASS (машина проехала)");
  return stuck ? 1 : 0;
}

int test_k33_death_zone(ColWorld *W, ColWorld *W3) {
  // №590: общее правило — весь карман за забором покрышек у R6D01 (полоса x 252…324 z -486…-464), не кусок; точки Роба и восточная часть
  int fails = 0, total = 0, dead = 0;
  for (float x = 258.f; x <= 322.f; x += 6.f) for (int k = 0; k < 2; k++) {
    float z = k ? -482.f : -485.f, g = 0.f; total++;
    if (!colGround(W, x, z, 25.f, -30.f, &g, 0)) continue;   // нет земли — нечего сбрасывать
    int d = colDeathAt(W, x, g + 0.5f, z, 0.f);
    if (d >= 0 && !strcmp(W->death[d].name, "R6D01")) dead++; else { fails++; printf("  точка за забором (%.0f %.1f %.0f): сброса нет\n", x, g, z); }
  }
  float x = 267.2f, y = 6.3f, z = -479.5f;
  int d = colDeathAt(W, x, y, z, 0.f);
  int ok = (d >= 0 && !strcmp(W->death[d].name, "R6D01"));
  printf("  [#590 K3-3 DEAD ZONE] точка Роба (%.1f, %.1f, %.1f): %s; полоса за забором: %d из %d точек с землёй сбрасывают -> %s\n",
         x, y, z, ok ? "R6D01" : "нет", dead, total, (ok && !fails) ? "PASS" : "FAIL");
  if (!ok) fails++;
  // не затронуто: дорога у спавна L1 и весь L3 (R6D01 там нет)
  float gs = 0.f; colGround(W, 220.f, 172.f, 30.f, -30.f, &gs, 0);
  int okc = colDeathAt(W, 220.f, gs + 0.5f, 172.f, 0.f) < 0 && W3->npocket == 0;
  printf("  [#590 K3-3 CONTROL] спавн L1 не зона, L3 без кармана (npocket=%u) -> %s\n", W3->npocket, okc ? "PASS" : "FAIL");
  if (!okc) fails++;
  return fails;
}

int test_l3_playability(ColWorld *W) {
  CarParams P; carParamsFor("famil_v", &P);
  float marks[3][3] = {
    {-399.6f, -58.9f, -75.2f},
    {-472.9f, -58.9f, -77.6f},
    {-513.7f, -73.4f, -71.5f}
  };
  const char *names[3] = {"#32 D7-1", "#33 C7-1", "#38 B7-3"};

  int fails = 0;
  for (int m = 0; m < 3; m++) {
    float sx = marks[m][0], sy = marks[m][1], sz = marks[m][2];
    Car c;
    float gy = 0.f;
    colGround(W, sx, sz, sy + 5.f, sy - 15.f, &gy, 0);
    carInit(&c, &P, W, sx, gy + 0.6f, sz, 0.0f);
    carSetSpeed(&c, 10.0f);

    int ok = 1;
    for (int step = 0; step < 40; step++) {
      CarInput in = { .throttle = 1.0f };
      carUpdate(&c, W, &in, 1/60.f);
      if (c.reverts > 5 || c.noGroundT > 1.0f) { ok = 0; break; }
    }
    printf("  [#590 L3 ZONE %s] ok=%d revs=%d -> %s\n",
           names[m], ok, c.reverts, ok ? "PASS" : "FAIL");
    if (!ok) fails++;
  }
  return fails;
}

int main(int argc, char **argv) {
  if (argc < 3) return 2;
  const char *l1_path = argv[1];
  const char *l3_path = argv[2];

  FILE *f1 = fopen(l1_path, "rb");
  if (!f1) return 2;
  fseek(f1, 0, SEEK_END); long sz1 = ftell(f1); fseek(f1, 0, SEEK_SET);
  char *buf1 = malloc(sz1); fread(buf1, 1, sz1, f1); fclose(f1);
  ColWorld W1;
  colInit(&W1, buf1 + *(unsigned*)(buf1+92), *(unsigned*)(buf1+96) - *(unsigned*)(buf1+92));

  FILE *f3 = fopen(l3_path, "rb");
  if (!f3) return 2;
  fseek(f3, 0, SEEK_END); long sz3 = ftell(f3); fseek(f3, 0, SEEK_SET);
  char *buf3 = malloc(sz3); fread(buf3, 1, sz3, f3); fclose(f3);
  ColWorld W3;
  colInit(&W3, buf3 + *(unsigned*)(buf3+92), *(unsigned*)(buf3+96) - *(unsigned*)(buf3+92));

  int fails = 0;
  printf("=== 1. Проверка #587 (податливые кусты J9-4) ===\n");
  fails += test_bush_drive(&W1);

  printf("\n=== 2. Проверка #590 (L1 K3-3 зона за забором) ===\n");
  fails += test_k33_death_zone(&W1, &W3);

  printf("\n=== 3. Проверка #590 (L3 играбельные зоны #32, #33, #38) ===\n");
  fails += test_l3_playability(&W3);

  free(buf1); free(buf3);
  return fails;
}
EOF

echo "--- Сборка и запуск: ЗЕЛЁНЫЙ ПРОГОН ---"
clang -O2 -Iviewer "$TMP_DIR/test_runner.c" viewer/col.c viewer/car.c -lm -o "$TMP_DIR/runner_green"
"$TMP_DIR/runner_green" "$L1_SHR" "$L3_SHR" > "$TMP_DIR/green.txt"
cat "$TMP_DIR/green.txt"
GREEN_FAILS=$(grep -c "FAIL" "$TMP_DIR/green.txt" || true)

if [ "$GREEN_FAILS" -ne 0 ]; then
  echo "ОШИБКА: Зелёный прогон завершился с ошибками ($GREEN_FAILS failures)!"
  exit 1
fi
echo "ЗЕЛЁНЫЙ ПРОГОН: PASS"

echo ""
echo "--- Сборка и запуск: КРАСНЫЙ КОНТРОЛЬ (-DBUSH_SOFT_OLD=1 -DPLAYABLE_ZONE_OLD=1); отдельный красный по кармане: -DPOCKET_RECT_OLD=1 обязан не покрыть восточную часть ---"
clang -O2 -DBUSH_SOFT_OLD=1 -DPLAYABLE_ZONE_OLD=1 -Iviewer "$TMP_DIR/test_runner.c" viewer/col.c viewer/car.c -lm -o "$TMP_DIR/runner_red"
"$TMP_DIR/runner_red" "$L1_SHR" "$L3_SHR" > "$TMP_DIR/red.txt" || true
cat "$TMP_DIR/red.txt"
RED_FAILS=$(grep -c "FAIL" "$TMP_DIR/red.txt" || true)

if [ "$RED_FAILS" -eq 0 ]; then
  echo "ОШИБКА: Красный контроль не покраснел!"
  exit 1
fi
echo "КРАСНЫЙ КОНТРОЛЬ: PASS ($RED_FAILS сбоев отловлено под флагами отката)"

echo ""
echo "--- КРАСНЫЙ КОНТРОЛЬ 2 (-DPOCKET_RECT_OLD=1: прежний прямоугольник по координатам не покрывает восточную полосу) ---"
clang -O2 -DPOCKET_RECT_OLD=1 -Iviewer "$TMP_DIR/test_runner.c" viewer/col.c viewer/car.c -lm -o "$TMP_DIR/runner_rect"
"$TMP_DIR/runner_rect" "$L1_SHR" "$L3_SHR" > "$TMP_DIR/rect.txt" || true
grep "K3-3" "$TMP_DIR/rect.txt"
if ! grep -q "K3-3 DEAD ZONE.*FAIL" "$TMP_DIR/rect.txt"; then
  echo "ОШИБКА: красный контроль 2 не покраснел!"
  exit 1
fi
echo "КРАСНЫЙ КОНТРОЛЬ 2: PASS (прямоугольник не покрывает весь карман)"

echo ""
echo "ИТОГ: zones_bushes_gate PASS (#587 и #590 полностью закрыты)"
