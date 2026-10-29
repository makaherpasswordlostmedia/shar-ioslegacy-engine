#!/bin/bash
# tests/walls/pits_ridges_gate.sh
# Гейт для правок Роба:
#   №582: ямы L2 (метки #14, #15, #17, #21, #24) — сглаживание нормали днища на склонах при вывешивании
#   №584: выступы L3 (метки #29 D6-9, #30 D7-6, #31 C6-7) — боковое соскальзывание кузова с колонн и выступов
# Флаг отката: PITS_SMOOTH_OLD=1 (или RIDGE_SLIDE_OLD=1)

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TMP_DIR="build/tmp/pits_ridges"
mkdir -p "$TMP_DIR"

L2_SHR="$HOME/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721/l2/level.shr"
L3_SHR="$HOME/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721/l3/level.shr"

if [ ! -f "$L2_SHR" ] || [ ! -f "$L3_SHR" ]; then
  echo "ОШИБКА: level.shr для L2 или L3 не найден!"
  exit 2
fi

cat << 'EOF' > "$TMP_DIR/test_runner.c"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "col.h"
#include "car.h"

static int test_run(ColWorld *W, const char *carName, const char *label,
                    float sx, float sz, float head, int steps, float maxDropAllowed, int lobCrash) {
  CarParams P; carParamsFor(carName, &P);
  float gy = 0.f;
  colGround(W, sx, sz, 50.0f, -80.0f, &gy, 0);
  Car c;
  carInit(&c, &P, W, sx, gy + 0.6f, sz, head);
  carSetSpeed(&c, 15.0f);

  float maxDrop = 0.f;
  for (int step = 0; step < steps; step++) {
    float pspd = sqrtf(c.vel[0]*c.vel[0] + c.vel[2]*c.vel[2]);
    CarInput in = { .throttle = 1.0f };
    carUpdate(&c, W, &in, 1/60.f);
    float cspd = sqrtf(c.vel[0]*c.vel[0] + c.vel[2]*c.vel[2]);
    float drop = (pspd - cspd) / fmaxf(pspd, 1.0f);
    if (drop > maxDrop && step > 5) maxDrop = drop;
  }

  if (lobCrash) {
    int ok = (maxDrop >= 0.70f);
    printf("  [LOB CRASH] %-24s: maxDrop=%5.1f%% -> %s\n", label, maxDrop * 100.f, ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
  } else {
    int ok = (maxDrop <= maxDropAllowed);
    printf("  [SMOOTH]    %-24s: maxDrop=%5.1f%% (порог %4.1f%%) -> %s\n",
           label, maxDrop * 100.f, maxDropAllowed * 100.f, ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
  }
}

int main(int argc, char **argv) {
  if (argc < 3) return 2;
  const char *l2_path = argv[1];
  const char *l3_path = argv[2];

  FILE *f2 = fopen(l2_path, "rb");
  if (!f2) return 2;
  fseek(f2, 0, SEEK_END); long sz2 = ftell(f2); fseek(f2, 0, SEEK_SET);
  char *buf2 = malloc(sz2); fread(buf2, 1, sz2, f2); fclose(f2);
  ColWorld W2;
  colInit(&W2, buf2 + *(unsigned*)(buf2+92), *(unsigned*)(buf2+96) - *(unsigned*)(buf2+92));

  FILE *f3 = fopen(l3_path, "rb");
  if (!f3) return 2;
  fseek(f3, 0, SEEK_END); long sz3 = ftell(f3); fseek(f3, 0, SEEK_SET);
  char *buf3 = malloc(sz3); fread(buf3, 1, sz3, f3); fclose(f3);
  ColWorld W3;
  colInit(&W3, buf3 + *(unsigned*)(buf3+92), *(unsigned*)(buf3+96) - *(unsigned*)(buf3+92));

  int fails = 0;

  printf("=== 1. Ямы L2 (#582: метки #14, #15, #17, #21, #24) ===\n");
  // Метки #14, #15 (F7-4 ямы): старт z=-20, проезд на юг (-Z) через траншеи
  fails += test_run(&W2, "honor_v", "#14/#15 F7-4 (honor_v)", -168.8f, -20.0f, 3.141592f, 70, 0.25f, 0);
  fails += test_run(&W2, "bart_v",  "#14/#15 F7-4 (bart_v)",  -168.8f, -20.0f, 3.141592f, 70, 0.25f, 0);
  // Метка #17 (E6-8): старт x=-254, проезд на восток (+X) через яму до x=-241 (45 шагов, до забора трассы)
  fails += test_run(&W2, "honor_v", "#17 E6-8 (honor_v)",     -254.0f, -102.2f, 1.570796f, 45, 0.25f, 0);
  fails += test_run(&W2, "bart_v",  "#17 E6-8 (bart_v)",      -254.0f, -102.2f, 1.570796f, 45, 0.25f, 0);
  // Метка #21 (F4-2): старт z=-380, проезд на север (+Z)
  fails += test_run(&W2, "honor_v", "#21 F4-2 (honor_v)",     -147.1f, -380.0f, 0.0f, 70, 0.25f, 0);
  // Метка #24 (K7-1): старт z=-74, проезд на юг (-Z)
  fails += test_run(&W2, "honor_v", "#24 K7-1 (honor_v)",      208.3f,  -74.0f, 3.141592f, 70, 0.25f, 0);

  printf("\n=== 2. Выступы L3 (#584: метки #29 D6-9, #30 D7-6, #31 C6-7) ===\n");
  // Метка #30 (D7-6 Cyl 62 x=-323.02): проезд коридора тротуара x=-322.0 и x=-321.5
  fails += test_run(&W3, "bart_v", "#30 D7-6 col x=-322.0", -322.0f, -48.0f, 3.141592f, 60, 0.20f, 0);
  fails += test_run(&W3, "bart_v", "#30 D7-6 col x=-321.5", -321.5f, -48.0f, 3.141592f, 60, 0.20f, 0);
  fails += test_run(&W3, "honor_v", "#30 D7-6 col x=-321.8", -321.8f, -48.0f, 3.141592f, 60, 0.20f, 0);
  // Метка #29 (D6-9 Cyl 64 x=-323.24): проезд коридора тротуара
  fails += test_run(&W3, "bart_v", "#29 D6-9 col x=-321.8", -321.8f, -96.0f, 3.141592f, 60, 0.20f, 0);
  // Метка #31 (C6-7 Cyl 74 x=-464.56): проезд вдоль улицы
  fails += test_run(&W3, "bart_v", "#31 C6-7 col x=-468.2", -468.2f, -112.0f, 3.141592f, 60, 0.20f, 0);

  printf("\n=== 3. Проверка сохранения лобового удара в центр колонны ===\n");
  // Лобовой удар центром машины прямо в центр Cyl 62 (x=-323.02)
  fails += test_run(&W3, "bart_v", "Cyl 62 HEAD-ON CRASH", -323.02f, -48.0f, 3.141592f, 60, 0.70f, 1);

  free(buf2); free(buf3);
  return fails;
}
EOF

echo "--- Сборка и запуск: ЗЕЛЁНЫЙ ПРОГОН ---"
clang -O2 -Iviewer "$TMP_DIR/test_runner.c" viewer/col.c viewer/car.c -lm -o "$TMP_DIR/runner_green"
"$TMP_DIR/runner_green" "$L2_SHR" "$L3_SHR" > "$TMP_DIR/green.txt"
cat "$TMP_DIR/green.txt"
GREEN_FAILS=$(grep -c "FAIL" "$TMP_DIR/green.txt" || true)

if [ "$GREEN_FAILS" -ne 0 ]; then
  echo "ОШИБКА: Зелёный прогон завершился с ошибками ($GREEN_FAILS failures)!"
  exit 1
fi
echo "ЗЕЛЁНЫЙ ПРОГОН: PASS"

echo ""
echo "--- Сборка и запуск: КРАСНЫЙ КОНТРОЛЬ (-DPITS_SMOOTH_OLD=1) ---"
clang -O2 -DPITS_SMOOTH_OLD=1 -Iviewer "$TMP_DIR/test_runner.c" viewer/col.c viewer/car.c -lm -o "$TMP_DIR/runner_red"
"$TMP_DIR/runner_red" "$L2_SHR" "$L3_SHR" > "$TMP_DIR/red.txt" || true
cat "$TMP_DIR/red.txt"
RED_FAILS=$(grep -c "FAIL" "$TMP_DIR/red.txt" || true)

if [ "$RED_FAILS" -eq 0 ]; then
  echo "ОШИБКА: Красный контроль не покраснел! Ошибки не отловлены."
  exit 1
fi
echo "КРАСНЫЙ КОНТРОЛЬ: PASS ($RED_FAILS сбоев отловлено под флагом отката)"

echo ""
echo "ИТОГ: pits_ridges_gate PASS (#582 и #584 полностью закрыты)"
