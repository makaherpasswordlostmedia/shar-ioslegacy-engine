// Правка 138 (tests/rooms/frame_check.sh): точки пола комнат -> камера движка (viewer/roomcam.c, тот же код, что в EBOOT).
// Вход: пакет SHG1 и файл строк «комната x y z» (ноги Гомера). Выход: «P комната x y z камера вид fovY eye(3) look(3) имя»,
// камера -1 — ни одной (камера ходьбы). Красный гейта — сборка с -DROOMCAM_OFFSET_WORLD (прежнее толкование TargetOffset).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "roomcam.h"

int main(int argc, char **argv) {
  if (argc < 3) { puts("frame_host ПАКЕТ ТОЧКИ"); return 2; }
  FILE *f = fopen(argv[1], "rb"); if (!f) { puts("нет пакета"); return 2; }
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b, 1, n, f) != (size_t)n) return 2; fclose(f);
  if (n < 16 || memcmp(b, "SHG1", 4)) { puts("не SHG1"); return 2; }
  unsigned nr; memcpy(&nr, b + 4, 4);
  static RoomCam c[8][ROOM_CAMS]; int k[8] = {0}; char names[8][33] = {{0}};
  for (unsigned r = 0; r < nr && r < 8; r++) {
    unsigned off, size; memcpy(names[r], b + 16 + 48 * r, 32); memcpy(&off, b + 16 + 48 * r + 32, 4); memcpy(&size, b + 16 + 48 * r + 36, 4);
    if ((long)off + size > n) return 1;
    k[r] = roomCamsParse(c[r], ROOM_CAMS, b + off, size); if (k[r] < 0) return 1;
  }
  FILE *pf = fopen(argv[2], "r"); if (!pf) return 2;
  char room[64]; float p[3];
  while (fscanf(pf, "%63s %f %f %f", room, &p[0], &p[1], &p[2]) == 4) {
    int r = -1; for (unsigned i = 0; i < nr && i < 8; i++) if (!strcmp(names[i], room)) r = (int)i;
    if (r < 0) { printf("NOROOM %s\n", room); return 1; }
    int i = roomCamPick(c[r], k[r], -1, p); float e[3] = {0}, l[3] = {0}, fy = 0.f;
    if (i >= 0) { roomCamIdeal(&c[r][i], p, e, l); fy = roomCamFovY(&c[r][i]); }
    printf("P %s %.3f %.3f %.3f %d %d %.4f %.4f %.4f %.4f %.4f %.4f %.4f %s\n", room, p[0], p[1], p[2], i, i >= 0 ? c[r][i].type : -1, fy,
           e[0], e[1], e[2], l[0], l[1], l[2], i >= 0 ? c[r][i].name : "-");
  }
  return 0;
}
