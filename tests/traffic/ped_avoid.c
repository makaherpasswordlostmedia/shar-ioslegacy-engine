// №510: пешеход трафика обходит игрока (пешком) на своём пути: не заходит в круг, не стоит в упор, проходит дальше.
//   tests/traffic/ped_avoid.c LEVEL TRAFFIC ; -DTRF_PED_AVOID_OLD=1 — красный контроль (встаёт в упор)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "traffic.h"
#include "homer.h"
static ColWorld world; static Traffic T; static Car player;
static const float DT = 1.f / 30.f;
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) { unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u); fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; } return m; }
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) return 2;
  const float *hd = (const float *)(hdr + 12); float spx = hd[6], spz = hd[8];   // спавн уровня
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned fsize = (unsigned)ftell(f); unsigned end = fsize; if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) return 2;
  FILE *g = fopen(argv[2], "rb"); if (!g) return 2; fseek(g, 0, SEEK_END); unsigned tsize = (unsigned)ftell(g); unsigned char *buf = readAt(g, 0, tsize); fclose(g);
  if (!buf || trafficInitMem(&T, buf, tsize, 0)) return 2;
  int bad = 0, cases = 0;
  for (int attempt = 0; attempt < 4; attempt++) {
    trafficReset(&T, &world);
    float gy; colGround(&world, spx + attempt * 25.f, spz, hd[7] + 20.f, -1e6f, &gy, 0);
    carInit(&player, NULL, &world, spx + attempt * 25.f, gy, spz, 0.f);
    float pp[3] = {player.x, player.y, player.z}, eye[3] = {player.x, player.y + 3, player.z - 7}, fw[3] = {0, 0, 1};
    int pi = -1;
    for (int fr = 0; fr < 600 && pi < 0; fr++) { trafficUpdate(&T, &world, &player, 0, pp, eye, fw, DT);
      for (int i = 0; i < T.maxPeds; i++) if (T.ped[i].mode == TRP_WALK && !T.ped[i].test && hypotf(T.ped[i].x - pp[0], T.ped[i].z - pp[2]) < 25.f) { pi = i; break; } }
    if (pi < 0) continue;
    TrPed *e = &T.ped[pi];
    player.x = 5000.f; player.z = 5000.f;   // машина игрока далеко: мерим обход ЧЕЛОВЕКА (машину пешеход по-прежнему пережидает)
    { float sx = e->x, sz = e->z; for (int k = 0; k < 6; k++) trafficUpdate(&T, &world, &player, 0, pp, eye, fw, DT);   // куда идёт на самом деле
      if (e->mode != TRP_WALK) continue; float dd = hypotf(e->x - sx, e->z - sz); if (dd < .02f) continue; sx = (e->x - sx) / dd; sz = (e->z - sz) / dd; e->h = atan2f(sx, sz); }
    float fx = sinf(e->h), fz = cosf(e->h);
    float bp[3] = {e->x + fx * 2.2f, e->y, e->z + fz * 2.2f}; float x0 = e->x, z0 = e->z, minD = 9.f; int standF = 0, walkF = 0;
    // игрок пешком (driving = 0) неподвижно на пути пешехода; остальных пешеходов убираем, чтобы мерить обход игрока
    for (int i = 0; i < T.maxPeds; i++) if (i != pi) T.ped[i].mode = TRP_OFF;
    for (int fr = 0; fr < 30 * 25; fr++) {
      float eye2[3] = {bp[0], bp[1] + 3, bp[2] - 7};
      trafficUpdate(&T, &world, &player, 0, bp, eye2, fw, DT);
      if (e->mode == TRP_OFF) break;
      float d = hypotf(e->x - bp[0], e->z - bp[2]); if (d < minD) minD = d;
      if (e->mode == TRP_STAND) standF++; else if (e->mode == TRP_WALK) walkF++;
    }
    float prog = (e->x - x0) * fx + (e->z - z0) * fz, bpProg = 2.2f;
    if (minD > 1.5f && !standF) { printf("случай %d: путь пешехода не сошёлся с игроком (ближе всего %.2f м) — не считается\n", attempt, minD); continue; }
    cases++;
    int ok = standF < 60 && minD > TR_PED_R + HOMER_RADIUS - .06f;   // не стоит в упор (> 2 с) и не заходит в круг игрока; поворот пути за углом — не показатель
    printf("случай %d: пешеход %d прошёл вдоль пути %.1f м (игрок на %.1f м), ближе всего %.2f м (граница %.2f), стоял кадров %d, шёл %d -> %s\n", attempt, pi, prog, bpProg, minD, TR_PED_R + HOMER_RADIUS, standF, walkF, ok ? "ok" : "FAIL");
    bad += !ok;
  }
  printf("%s (случаев %d)\n", bad || !cases ? "FAIL" : "PASS", cases); return bad || !cases;
}
