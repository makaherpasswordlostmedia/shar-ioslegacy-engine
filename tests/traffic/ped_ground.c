// Правка Роба 594 (13.10, L3 D5-9, метка x −304.95 y −53 z −221.75): «люди ходят выше, чем у меня голова: стопы на уровне плеч, на пару уровней выше моих ног».
// Замер на Маке по данным уровня (level.shr COL1 + traffic.shr TRF1): игрок стоит в точке метки, трафик живёт, считаем кадры, в которых живой пешеход
// (не в полёте) ближе 45 м стоит выше земли под собой (ближайший слой земли под ногами дальше 0,35 м) или выше ног игрока больше чем на 1,5 м.
//   ped_ground level.shr traffic.shr [секунд] [x y z игрока]    код возврата = число плохих кадров (0 — нет); печать первых случаев и худшей высоты
#include "../../viewer/traffic.c"

static ColWorld world; static Traffic T;
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) {
  unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u); fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; } return m;
}
int main(int argc, char **argv) {
  if (argc < 3) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) return 2;
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned fsize = (unsigned)ftell(f), end = fsize; if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) return 2;
  FILE *g = fopen(argv[2], "rb"); if (!g) return 2; fseek(g, 0, SEEK_END); unsigned tsize = (unsigned)ftell(g); unsigned char *buf = readAt(g, 0, tsize); fclose(g);
  if (trafficInitMem(&T, buf, tsize, 0)) return 2;
  float secs = argc > 3 ? (float)atof(argv[3]) : 240.f;
  float px = argc > 4 ? (float)atof(argv[4]) : -304.95f, py = argc > 5 ? (float)atof(argv[5]) : -53.f, pz = argc > 6 ? (float)atof(argv[6]) : -221.75f;
  int bad = 0, frames = 0, seenPeds = 0; float worstUp = 0.f, worstAbove = 0.f;
  for (unsigned seed = 1; seed <= 6; seed++) {
    trafficReset(&T, &world); T.seed = seed * 7919u + 17u;
    Car pl; carInit(&pl, NULL, &world, px, py + 0.6f, pz, 0.f); pl.y -= 100.f;   // призрак: стоит, трафик его не задевает
    float pp[3] = {px, py, pz}, eye[3] = {px, py + 3.f, pz - 8.f}, fwd[3] = {0.f, 0.f, 1.f};
    int nf = (int)(secs / (1.f / 60.f));
    for (int fr = 0; fr < nf; fr++) {
      trafficUpdate(&T, &world, &pl, 1, pp, eye, fwd, 1.f / 60.f);
      TrEvent e; while (trafficPopEvent(&T, &e)) {}
      frames++;
      for (int i = 0; i < T.maxPeds; i++) {
        const TrPed *p = &T.ped[i]; if (p->mode != TRP_WALK && p->mode != TRP_STAND && p->mode != TRP_DODGE && p->mode != TRP_GETUP) continue;
        float dx = p->x - px, dz = p->z - pz; if (dx * dx + dz * dz > 45.f * 45.f) continue;
        seenPeds++;
        float gy; int ok = colGround(&world, p->x, p->z, p->y + 0.5f, p->y - 400.f, &gy, 0);
        float up = ok ? p->y - gy : 999.f, above = p->y - py;
        if (up > worstUp && up < 900.f) worstUp = up; if (above > worstAbove) worstAbove = above;
        if (up > 0.35f || above > 1.5f) { if (bad < 8) printf("  seed %u t=%.1f пешеход %d путь %d (%.1f %.2f %.1f): над землёй под собой %.2f м, над ногами игрока %.2f м\n", seed, fr / 60.f, i, p->path, p->x, p->y, p->z, up, above); bad++; }
      }
    }
  }
  printf("кадров %d, пешеходов в замерах %d, плохих %d, худшее над землёй %.2f м, худшее над ногами игрока %.2f м\n", frames, seenPeds, bad, worstUp, worstAbove);
  return bad ? 1 : 0;
}
