#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"

// Гейт для правки Роба №581: "Стыки как прозрачная стена на всех уровнях"
// Проверяет проезд ключевых стыков и швов без остановок и ударов:
// 1) Mark #5 (L1 J11-3 goto 180.4 320.8) — заезд на торец рампы/лестницы (было: удар о Tri 41462 / Box 1019)
// 2) Mark #22 (L2 G4-8 goto -51.6 -331.4) — проезд мимо угла бордюра Box 926 (было: зацеп колесом и потеря 67% скорости)
// 3) Mark #1 / #2 (L1 J9-8 goto 159.6 168.5) — заезд на склон холма полянки (было: удар днищем о склон)
// 4) Mark #27 / #28 (L3 H7-7 goto 28.8 -29.4) — переезд 21-см стыка дороги на скорости 80 км/ч (было: удар о Tri 19891)

static ColWorld W1, W2, W3;
static char *buf1, *buf2, *buf3;

static void loadWorld(int lvl, ColWorld *W, char **pbuf) {
  char path[256];
  if (lvl == 1) snprintf(path, sizeof(path), "/Users/USER/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721/level.shr");
  else snprintf(path, sizeof(path), "/Users/USER/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721/l%d/level.shr", lvl);
  FILE *f = fopen(path, "rb");
  if (!f) { fprintf(stderr, "Cannot open %s\n", path); exit(2); }
  fseek(f, 0, SEEK_END); long fsz = ftell(f); fseek(f, 0, SEEK_SET);
  *pbuf = (char *)malloc(fsz); fread(*pbuf, 1, fsz, f); fclose(f);
  unsigned co = *(unsigned *)(*pbuf + 92), ce = *(unsigned *)(*pbuf + 96);
  colInit(W, *pbuf + co, ce - co);
}

// Заезд на объект и измерение максимального дропа скорости в зоне контакта
static float runTest(ColWorld *W, float sx, float sz, float gy, float hd, float spd, int steps, float check_min_z, float check_max_z, float check_min_x, float check_max_x) {
  Car car;
  carInit(&car, NULL, W, sx, gy + 0.6f, sz, hd);
  carSetSpeed(&car, spd);

  float maxDrop = 0.0f;
  for (int st = 0; st < steps; st++) {
    float prev_spd = sqrtf(car.vel[0]*car.vel[0] + car.vel[2]*car.vel[2]);
    CarInput in = { .throttle = 1.0f };
    carUpdate(&car, W, &in, 1/60.f);
    float cur_spd = sqrtf(car.vel[0]*car.vel[0] + car.vel[2]*car.vel[2]);

    int in_zone = (car.z >= check_min_z && car.z <= check_max_z &&
                   car.x >= check_min_x && car.x <= check_max_x);
    if (in_zone && st > 5) {
      float drop = (prev_spd - cur_spd) / fmaxf(prev_spd, 1.0f);
      if (cur_spd < 1.0f && prev_spd > 3.0f) drop = 1.0f;
      if (drop > maxDrop) maxDrop = drop;
    }
  }
  return maxDrop;
}

int main(int argc, char **argv) {
  loadWorld(1, &W1, &buf1);
  loadWorld(2, &W2, &buf2);
  loadWorld(3, &W3, &buf3);

  int fails = 0;

  // 1. Mark #5: Въезд на торец рампы J11-3 у z=320.8 (x=179.5..180.5)
  // Направление North (hd = 0.0). Старт на дороге за 15м (z = 305.0).
  // Без фикса: лобовой удар о Tri 41462 / торец с потерей 90% скорости на z=319.2..320.5
  {
    float gy = 3.91f;
    colGround(&W1, 180.0f, 312.0f, 15.0f, -100.0f, &gy, 0);
    float drop = runTest(&W1, 180.0f, 312.0f, gy, 0.0f, 10.0f, 60, 318.0f, 320.5f, 178.0f, 182.0f);
    printf("Mark #5 (L1 J11-3 ramp entrance): maxDrop=%.1f%%\n", drop * 100.0f);
    if (drop > 0.30f) {
      printf("  FAIL: Mark #5 hit ramp entrance seam (drop > 30%%)\n");
      fails++;
    } else {
      printf("  PASS: Mark #5 ramp entrance smooth\n");
    }
  }

  // 2. Mark #22: Проезд мимо угла бордюра G4-8 (x=-51.6, z=-331.4)
  // Направление East (hd = pi/2). Старт за 25м (x = -76.6).
  // Без фикса: зацеп передним колесом за угол Box 926 с потерей 65-67% скорости
  {
    float gy = 28.9f;
    colGround(&W2, -76.6f, -331.4f, 40.0f, -100.0f, &gy, 0);
    float drop = runTest(&W2, -76.6f, -331.4f, gy, 1.570796f, 20.0f, 120, -333.0f, -330.0f, -53.0f, -46.0f);
    printf("Mark #22 (L2 G4-8 curb corner): maxDrop=%.1f%%\n", drop * 100.0f);
    if (drop > 0.30f) {
      printf("  FAIL: Mark #22 wheel hit curb corner (drop > 30%%)\n");
      fails++;
    } else {
      printf("  PASS: Mark #22 curb corner smooth glance\n");
    }
  }

  // 3. Mark #1 / #2: Заезд на холм полянки J9-8 (x=159.6, z=168.5)
  // Направление East (hd = pi/2). Старт за 25м у дороги (x = 134.6, z = 168.5).
  // Без фикса: удар днищем о склон холма с гашением скорости
  {
    float gy = 5.2f;
    colGround(&W1, 134.6f, 168.5f, 20.0f, -100.0f, &gy, 0);
    float drop = runTest(&W1, 134.6f, 168.5f, gy, 1.570796f, 15.0f, 100, 165.0f, 172.0f, 145.0f, 165.0f);
    printf("Mark #1/#2 (L1 J9-8 meadow hill climb): maxDrop=%.1f%%\n", drop * 100.0f);
    if (drop > 0.30f) {
      printf("  FAIL: Mark #1/#2 belly hit hill slope (drop > 30%%)\n");
      fails++;
    } else {
      printf("  PASS: Mark #1/#2 meadow hill climb smooth\n");
    }
  }

  // 4. Mark #27 / #28: Переезд 21-см стыка дороги H7-7 на высокой скорости (x=28.8, z=-29.4)
  // Направление North (hd = 0.0). Старт за 20м (z = -49.4). Скорость 20 м/с (~72-85 км/ч).
  // Без фикса: колесо бьет грань Tri 19891 как отвесную стену при пересечении z=-30.0
  {
    float gy = 6.83f;
    colGround(&W3, 28.8f, -49.4f, 15.0f, -100.0f, &gy, 0);
    float drop = runTest(&W3, 28.8f, -49.4f, gy, 0.0f, 20.0f, 65, -31.5f, -28.5f, 25.0f, 32.0f);
    printf("Mark #27/#28 (L3 H7-7 21cm road seam): maxDrop=%.1f%%\n", drop * 100.0f);
    if (drop > 0.30f) {
      printf("  FAIL: Mark #27/#28 wheel hit road seam step (drop > 30%%)\n");
      fails++;
    } else {
      printf("  PASS: Mark #27/#28 high-speed road seam smooth\n");
    }
  }

  printf("\nRESULT: %s (%d failures)\n", fails ? "FAIL" : "PASS", fails);
  return fails;
}
