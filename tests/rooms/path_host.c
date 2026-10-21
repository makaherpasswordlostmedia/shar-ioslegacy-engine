// Близнецы (правки 172/186): путь Гомера оригинала в комнате -> камера порта (viewer/roomcam.c, тот же код, что в EBOOT) по кадрам.
//   path_host ПАКЕТ КОМНАТА ПУТЬ.tsv [old|old172]   ПУТЬ: «кадр x z» в осях порта (кадр PS2 50 к/с); old — прежнее правило выбора камеры, old172 — задержка 172 до школы
// Вывод: кадр, камера, глаз xyz, точка взгляда xyz
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "roomcam.h"
int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "path_host ПАКЕТ КОМНАТА ПУТЬ.tsv [old]\n"); return 2; }
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f); unsigned char *b = malloc((size_t)n);
  if (fread(b, 1, (size_t)n, f) != (size_t)n) return 2; fclose(f);
  unsigned nr; memcpy(&nr, b + 4, 4); static RoomCam c[ROOM_CAMS]; int k = -1;
  for (unsigned r = 0; r < nr; r++) { char name[33] = {0}; unsigned off, size; memcpy(name, b + 16 + 48 * r, 32); memcpy(&off, b + 16 + 48 * r + 32, 4); memcpy(&size, b + 16 + 48 * r + 36, 4);
    if (!strcmp(name, argv[2])) k = roomCamsParse(c, ROOM_CAMS, b + off, size); }
  if (k <= 0) { puts("нет камер"); return 1; }
  RoomCamState st; memset(&st, 0, sizeof st); st.cur = -1; st.want = -1; st.newWins = !(argc > 4 && !strcmp(argv[4], "old")); st.switchOld = argc > 4 && !strcmp(argv[4], "old172");   // old172 — правило задержки 172 до школы
  FILE *t = fopen(argv[3], "r"); if (!t) return 2;
  char ln[256]; int fr, prev = -1; float hx, hz;
  while (fgets(ln, sizeof ln, t)) {
    if (sscanf(ln, "%d %f %f", &fr, &hx, &hz) != 3) continue;
    float dt = prev >= 0 ? (float)(fr - prev) / 50.f : 1.f / 50.f; prev = fr;
    float p[3] = {hx, -20.f, hz}, e[3], l[3], fy; int j = roomCamStep(c, k, &st, p, dt, e, l, &fy);
    printf("%d\t%s\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\n", fr, j >= 0 ? c[j].name : "-", e[0], e[1], e[2], l[0], l[1], l[2]);
  }
  return 0;
}
