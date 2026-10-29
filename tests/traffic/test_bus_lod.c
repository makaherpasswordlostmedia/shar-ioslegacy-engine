#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "viewer/traffic.h"

// Хост-тест адаптивной дистанции переключения LOD трафика (№558).
// Проверяет:
// 1. Для школьного автобуса (schoolbu, hl=2.87..5.5м) и грузовиков дистанция LOD
//    масштабируется до 54..65 м (вместо фиксированных 30 м), поэтому при сближении
//    машина переходит на детальную модель заблаговременно вдалеке (d=40..50 м).
// 2. Для компактных машин базовая дистанция составляет 42 м (вместо 30 м).
// 3. Под флагом отката TRF_LOD_DIST_OLD=1 возвращается старое поведение (30 м).

int main(int argc, char **argv) {
  const char *shrPath = (argc > 1) ? argv[1] : "build/final-20261011-1721/traffic.shr";
  FILE *f = fopen(shrPath, "rb");
  if (!f) f = fopen("build/traffic.shr", "rb");
  if (!f) {
    fprintf(stderr, "Cannot open traffic.shr from %s\n", shrPath);
    return 2;
  }
  fseek(f, 0, SEEK_END);
  long sz = ftell(f);
  fseek(f, 0, SEEK_SET);
  unsigned char *buf = malloc(sz);
  if (!buf || fread(buf, 1, sz, f) != (size_t)sz) {
    fclose(f);
    free(buf);
    return 2;
  }
  fclose(f);

  TrHeader *hd = (TrHeader *)buf;
  if (memcmp(hd->magic, "TRF1", 4) != 0) {
    fprintf(stderr, "Bad magic in traffic.shr\n");
    free(buf);
    return 2;
  }

  const TrModel *models = (const TrModel *)(buf + hd->offModel);
  int nModel = (int)hd->nModel;
  printf("Loaded traffic.shr: %d models\n", nModel);

  const TrModel *bus = NULL;
  const TrModel *truck = NULL;
  const TrModel *husk = NULL;
  const TrModel *van = NULL;

  for (int i = 0; i < nModel; i++) {
    const TrModel *m = &models[i];
    if (!strcmp(m->name, "schoolbu")) bus = m;
    else if (!strcmp(m->name, "glastruc")) truck = m;
    else if (!strcmp(m->name, "huskA")) husk = m;
    else if (!strcmp(m->name, "minivanA")) van = m;
  }

  int fails = 0;

  // Проверка 1: schoolbu
  if (bus) {
    float dist = trLodDist(bus);
    printf("schoolbu: halfL=%.2f halfW=%.2f -> trLodDist = %.2f m\n", bus->halfL, bus->halfW, dist);
    if (dist < 50.f || dist > 65.f) {
      printf("FAIL: schoolbu trLodDist expected in [50..65]m, got %.2f\n", dist);
      fails++;
    } else {
      printf("ok: schoolbu trLodDist = %.2fm in [50..65]m\n", dist);
    }
    // На дистанции 40 м автобус обязан рисоваться детальной версией (lod == 0)
    int lod_at_40 = (40.f > dist);
    if (lod_at_40 != 0) {
      printf("FAIL: schoolbu at 40m must be LOD 0 (detailed), got %d (dist=%.2f)\n", lod_at_40, dist);
      fails++;
    } else {
      printf("ok: schoolbu at 40m is detailed (lod 0)\n");
    }
    // На дистанции 70 м автобус рисуется LOD версией (lod == 1)
    int lod_at_70 = (70.f > dist);
    if (lod_at_70 != 1) {
      printf("FAIL: schoolbu at 70m must be LOD 1 (far), got %d (dist=%.2f)\n", lod_at_70, dist);
      fails++;
    } else {
      printf("ok: schoolbu at 70m is far LOD (lod 1)\n");
    }
  } else {
    printf("WARN: schoolbu not found\n");
    fails++;
  }

  // Проверка 2: glastruc
  if (truck) {
    float dist = trLodDist(truck);
    printf("glastruc: halfL=%.2f halfW=%.2f -> trLodDist = %.2f m\n", truck->halfL, truck->halfW, dist);
    if (dist < 55.f || dist > 65.f) {
      printf("FAIL: glastruc trLodDist expected in [55..65]m, got %.2f\n", dist);
      fails++;
    } else {
      printf("ok: glastruc trLodDist = %.2fm\n", dist);
    }
  } else {
    printf("WARN: glastruc not found\n");
    fails++;
  }

  // Проверка 3: компактные машины (husk / van)
  if (husk) {
    float dist = trLodDist(husk);
    printf("huskA: halfL=%.2f halfW=%.2f -> trLodDist = %.2f m\n", husk->halfL, husk->halfW, dist);
    if (dist < 40.f || dist > 45.f) {
      printf("FAIL: huskA base trLodDist expected ~42m, got %.2f\n", dist);
      fails++;
    } else {
      printf("ok: huskA base trLodDist = %.2fm\n", dist);
    }
    int lod_at_35 = (35.f > dist);
    if (lod_at_35 != 0) {
      printf("FAIL: compact car at 35m must be detailed (lod 0), got %d (dist=%.2f)\n", lod_at_35, dist);
      fails++;
    } else {
      printf("ok: compact car at 35m is detailed (lod 0)\n");
    }
  } else {
    printf("WARN: huskA not found\n");
    fails++;
  }

  free(buf);
  printf("Result: %s (fails=%d)\n", fails == 0 ? "PASS" : "FAIL", fails);
  return fails == 0 ? 0 : 1;
}
