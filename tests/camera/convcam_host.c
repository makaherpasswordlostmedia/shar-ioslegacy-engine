// Камеры разговора на Маке (правки Роба 40 и 38, tests/camera/convcam.sh): тот же viewer/convcam.c, что в EBOOT.
// Вход (stdin), строка на разговор:
//   S имя pcx pcy pcz npcx npcy npcz pcHead npcHead есть_лучшая bx by bz камер кам0..камN-1 реплик pc0..pcM-1
// (кам — имя плана реплики i из SetConversationCam или «-», pc — 1, если реплику говорит игрок). Выход на реплику:
//   P имя реплика план сторона данные eye(3) look(3) fovY ближняя_плоскость
// --plant rev — отрицательный контроль: план на слушающем (роли наоборот); --plant axis — глаз на оси за слушающим
// (как камера пешком за спиной Гомера: «Мардж за Гомером не видно», правка 40); --plant near — ближняя плоскость города
// 1.5 м, как до правки (на крупном плане срезает затылок слушающего — лицо видно «сквозь» голову). Проверка — tests/camera/convcam_check.py.
//   cc -std=c99 -O2 -I viewer tests/camera/convcam_host.c viewer/convcam.c -lm -o build/convcam_host
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "convcam.h"

int main(int argc, char **argv) {
  int plant = 0;
  if (argc > 2 && !strcmp(argv[1], "--plant")) plant = !strcmp(argv[2], "rev") ? 1 : !strcmp(argv[2], "axis") ? 2 : !strcmp(argv[2], "near") ? 3 : 0;
  char tag[4], name[64];
  while (scanf("%3s %63s", tag, name) == 2) {
    ConvScene s; memset(&s, 0, sizeof s); int ncam, nl;
    if (scanf("%f %f %f %f %f %f %f %f %d %f %f %f %d", &s.pc[0], &s.pc[1], &s.pc[2], &s.npc[0], &s.npc[1], &s.npc[2], &s.pcHead, &s.npcHead,
              &s.hasBest, &s.best[0], &s.best[1], &s.best[2], &ncam) != 13 || ncam < 0 || ncam > 16) { puts("BAD вход"); return 1; }
    static char cbuf[16][24]; const char *cams[16];
    for (int i = 0; i < ncam; i++) { if (scanf("%23s", cbuf[i]) != 1) { puts("BAD камеры"); return 1; } cams[i] = strcmp(cbuf[i], "-") ? cbuf[i] : 0; }
    if (scanf("%d", &nl) != 1 || nl < 0 || nl > 32) { puts("BAD реплики"); return 1; }
    int side = convSide(&s, 0);
    for (int line = 0; line < nl; line++) {
      int pc = 0, fromData = 0; if (scanf("%d", &pc) != 1) { puts("BAD реплика"); return 1; }
      int shot = convShotFor(cams, ncam, line, pc, &fromData);
      if (plant == 1) shot = shot == CONV_NPC_FAR ? CONV_PC_FAR : shot == CONV_NPC_NEAR ? CONV_PC_NEAR : shot == CONV_PC_FAR ? CONV_NPC_FAR : CONV_NPC_NEAR;
      float e[3], l[3], fy; convPose(&s, shot, side, e, l, &fy);
      if (plant == 2) {
        const float *F = convShotOnPc(shot) ? s.npc : s.pc, *S = convShotOnPc(shot) ? s.pc : s.npc;
        float ax = S[0] - F[0], az = S[2] - F[2], d = sqrtf(ax * ax + az * az) + 1e-6f; ax /= d; az /= d;
        e[0] = F[0] - ax * 2.5f; e[2] = F[2] - az * 2.5f;
      }
      float nz = plant == 3 ? 1.5f : convNear(&s, e);   // near — ближняя плоскость города 1.5 м, как без правки
      printf("P %s %d %s %d %d %.4f %.4f %.4f %.4f %.4f %.4f %.2f %.3f\n", name, line, convShotName(shot), side, fromData, e[0], e[1], e[2], l[0], l[1], l[2], fy, nz);
    }
  }
  return 0;
}
