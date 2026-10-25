// №913: ленты от 130 (и второй контур от 150) и таблицы зон дальности по настоящим файлам (Мак, только файлы).
// Режимы: chord — самая близкая к глазу хорда ленты по обоим контурам клетки (радиус ленты R+4: 134 для контура от 130, 154 для контура от 150; нужно не ближе своего радиуса, допуск 0,5 %);
//         trace — повтор трассы глаза (кадр x z) по таблице зон: переключений цели, скачок радиуса за кадр, число кадров на 130/150/250 (hzzone913.h, как в движке)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "../../viewer/horizon_chord.h"
#include "../../viewer/hzzone913.h"
static unsigned char *slurp(const char *fn, long *n) { FILE *f = fopen(fn, "rb"); if (!f) return 0; fseek(f, 0, SEEK_END); *n = ftell(f); fseek(f, 0, SEEK_SET); unsigned char *b = malloc((size_t)*n); if (fread(b, 1, (size_t)*n, f) != (size_t)*n) { fclose(f); return 0; } fclose(f); return b; }
int main(int argc, char **argv) {
  if (argc >= 3 && !strcmp(argv[1], "chord")) {
    unsigned viol = 0, cells = 0, noset2 = 0; float worstRatio = 9.f;
    for (int a = 2; a < argc; a++) {
      long sz; unsigned char *b = slurp(argv[a], &sz); if (!b || memcmp(b, "HOR1", 4)) { printf("FAIL: %s\n", argv[a]); return 2; }
      unsigned n = *(unsigned *)(b + 4); float R0 = *(float *)(b + 8);
      for (unsigned i = 0; i < n; i++) {
        const unsigned char *c = b + 32 + 32ull * i; unsigned nv = *(unsigned *)(c + 12), off = *(unsigned *)(c + 16), off2 = *(unsigned *)(c + 24), nv2 = *(unsigned *)(c + 28);
        for (int set = 0; set < 2; set++) {
          unsigned nn = set ? nv2 : nv, oo = set ? off2 : off; if (!nn) { if (set) noset2++; continue; }
          unsigned short az[HZ_CHORD_NV]; short t[HZ_CHORD_NV]; unsigned m = hzChordExpand(b + oo, nn, az, t); float R = set ? R0 + 20.f : R0, cellMin = 1e9f;
          for (unsigned k = 0; k + 1 < m; k++) { float d = (float)((unsigned short)(az[k + 1] - az[k])) * (360.f / 65536.f), dist = R * cosf(d * .5f * (float)M_PI / 180.f); if (dist < cellMin) cellMin = dist; }
          cells++; float ratio = cellMin / R; if (ratio < worstRatio) worstRatio = ratio; if (ratio < .995f) viol++; } }
      free(b); }
    printf("CHORD cells=%u viol=%u worst_ratio=%.4f no_second=%u\n", cells, viol, worstRatio, noset2); return viol ? 1 : 0;
  }
  if (argc >= 4 && !strcmp(argv[1], "trace")) {   // trace ЗОНЫ.bin ТРАССА.txt [base]
    long zs, ts; unsigned char *zb = slurp(argv[2], &zs); if (!zb || memcmp(zb, "HZN1", 4)) { printf("FAIL: зоны\n"); return 2; }
    unsigned w = *(unsigned *)(zb + 4), h = *(unsigned *)(zb + 8); float zg[3]; memcpy(zg, zb + 12, 12); HzZone Z = {zg[0], zg[1], zg[2], w, h, zb + 24};
    FILE *f = fopen(argv[3], "r"); if (!f) { printf("FAIL: трасса\n"); return 2; } (void)ts; float base = argc > 4 ? (float)atof(argv[4]) : 130.f;
    Hz913 st = {0}; char ln[200]; unsigned fr, n = 0, tgtFlip = 0, cnt[3] = {0}; float x, z, prevCap = -1, maxStep = 0; int prevTgt = -1;
    while (fgets(ln, sizeof ln, f)) { if (sscanf(ln, "%u %f %f", &fr, &x, &z) != 3) continue;
      int mode = hzZoneMode(&Z, x, z, 1); float cap = hz913Step(&st, mode, base, 1.f / 30.f);
      if (prevTgt >= 0 && st.tgt != prevTgt) tgtFlip++; prevTgt = st.tgt; if (prevCap >= 0 && fabsf(cap - prevCap) > maxStep) maxStep = fabsf(cap - prevCap); prevCap = cap; cnt[st.tgt]++; n++; }
    printf("TRACE frames=%u target_switches=%u max_step_m=%.2f frames_130=%u frames_150=%u frames_250=%u\n", n, tgtFlip, maxStep, cnt[0], cnt[1], cnt[2]);
    return 0;
  }
  return 2;
}
