// Правка 176 (Роб 01.10: «машины трафика на скорости — сразу горелый каркас, даже не взрываются»): оракул PS2 (близнец В14,
// knowledge/facts/ps2-traffic-hit.yaml, ступень 4) — минивэн HitPoints 1.0 от удара в бок машиной Гомера (HitPoints 3.0) на
// 20 и 35 м/с остаётся целым, без дыма. Настоящая физика viewer/car.c + col.c на ровной площадке (Мак, CPU):
//   one   — один удар в бок на 20 и 35 м/с: урон минивэна < SMOKE (дыма нет), не разбит
//   many  — серия ударов 35 м/с: минивэн всё-таки разбивается (не бессмертный), не раньше 3-го удара
// Красный (tests/trafhit/run.sh): -DCAR_HIT_DMG_K=1 (прежний урон: с ~41 м/с одним ударом, на 35 м/с — у порога)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"
#define SMOKE 0.5f
static int fails;
static void check(const char *n, int ok, const char *d) { printf("CHECK %-4s %s  %s\n", n, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } fx;
static ColWorld W;
static float hit(Car *van, float v) {   // машина Гомера в 12 м слева, лоб в бок минивэна; 2 с
  Car a; carInit(&a, 0, &W, -12.f, 0.f, 0.f, 1.5707963f); a.p.hitPoints = 3.f; carSetSpeed(&a, v);
  CarInput in = {1, 0, 0, 0}, none = {0, 0, 0, 1};
  for (int f = 0; f < 120; f++) { carUpdate(&a, &W, &in, 1.f / 60.f); carUpdate(van, &W, &none, 1.f / 60.f); carHitCar(&a, van, &W); }
  return van->damage;
}
int main(void) {
  memcpy(fx.h.magic, "COL1", 4); fx.h.ox = fx.h.oz = -60; fx.h.cell = 120; fx.h.W = fx.h.H = 1; fx.h.ntri = 2; fx.h.nref = 2;
  fx.t[0] = (ColTri){{-60, 0, -60}, {60, 0, 60}, {60, 0, -60}, {0, 1, 0}};
  fx.t[1] = (ColTri){{-60, 0, -60}, {-60, 0, 60}, {60, 0, 60}, {0, 1, 0}};
  fx.start[1] = 2; fx.refs[0] = 0; fx.refs[1] = 1;
  if (colInit(&W, &fx, sizeof fx)) { printf("FAIL: мир\n"); return 1; }
  char d[160]; float vs[2] = {20.f, 35.f};
  for (int i = 0; i < 2; i++) {
    Car van; carInit(&van, 0, &W, 0.f, 0.f, 0.f, 0.f); van.p.hitPoints = 1.f;
    float dm = hit(&van, vs[i]);
    snprintf(d, sizeof d, "удар в бок %.0f м/с: урон минивэна %.2f%s", vs[i], dm, van.destroyed ? ", РАЗБИТ" : "");
    check("one", dm < SMOKE && !van.destroyed, d);
  }
  { Car van; carInit(&van, 0, &W, 0.f, 0.f, 0.f, 0.f); van.p.hitPoints = 1.f; int k = 0;
    for (; k < 8 && !van.destroyed; k++) { van.x = 0.f; van.z = 0.f; memset(van.vel, 0, sizeof van.vel); memset(van.w, 0, sizeof van.w); hit(&van, 35.f); }
    snprintf(d, sizeof d, "серия 35 м/с: разбит %s, ударов %d", van.destroyed ? "да" : "нет", k);
    check("many", van.destroyed && k >= 3, d); }
  { // правка 185: серия таранов оригинала (v14_ram4, скорость машины Гомера на кадре контакта), урон трафика — carRamDamage
    static const float ram[14] = {9.40f, 1.32f, 3.05f, 2.30f, 4.00f, 8.83f, 14.50f, 3.79f, 6.57f, 5.17f, 6.10f, 6.26f, 5.52f, 5.54f};
    Car van; carInit(&van, 0, &W, 0.f, 0.f, 0.f, 0.f); van.p.hitPoints = 1.f;
    for (int k = 0; k < 14; k++) { van.x = 0.f; van.z = 0.f; memset(van.vel, 0, sizeof van.vel); memset(van.w, 0, sizeof van.w);
      float d0 = van.damage; hit(&van, ram[k]); carRamDamage(&van, d0); }
    snprintf(d, sizeof d, "14 таранов оригинала 1,3–14,5 м/с: урон минивэна %.2f%s (дым с 0,33)", van.damage, van.destroyed ? ", РАЗБИТ" : "");
    check("ram", van.damage < 0.33f && !van.destroyed, d); }
  printf("RESULT %s провалов %d\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
