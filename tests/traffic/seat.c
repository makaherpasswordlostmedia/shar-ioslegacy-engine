// №666 гейт посадки в угнанную машину трафика: у каждой модели пакета есть высота сиденья водителя (TRF1 offSeat, сустав dl), по правилу посадки
// (homer.c seatLift: таз 0,46 м + (seatY + lift − 0,499), макушка Гомера выше таза на 1,416 м) макушка героя в угнанной машине — не ниже 65 % высоты
// кузова или кабины 2 м (автобус и грузовик не «тонут»); выше кузова на 10 % — пометка для глаз. Куски водителя (owner 4) не рисуются у машины игрока. Остов (huskModel) без сустава — пропуск. Красный контроль: -DTRF_SEAT_OLD=1 (блок не читается: сиденье запасное) или пакет без блока
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "traffic.h"
static int nDrv, nAll, withDrv;
static void fn(void *u, const TrPiece *p, const void *verts, const float m[16]) { (void)u; (void)verts; (void)m; nAll++; if (p->owner == 4) nDrv++; }
int main(int argc, char **argv) {
  const char *trf = argc > 1 ? argv[1] : "build/traffic.shr";
  FILE *g = fopen(trf, "rb"); if (!g) { printf("no %s\n", trf); return 2; }
  fseek(g, 0, SEEK_END); unsigned size = (unsigned)ftell(g); fseek(g, 0, SEEK_SET);
  unsigned char *buf = aligned_alloc(64, (size + 63) & ~63u); if (fread(buf, 1, size, g) != size) return 2; fclose(g);
  static Traffic T; int r = trafficInitMem(&T, buf, size, 0); if (r) { printf("FAIL load %d\n", r); return 1; }
  int bad = 0, n = 0;
  for (unsigned i = 0; i < T.hd->nModel; i++) {
    const TrModel *M = &T.model[i]; const CarParams *P = &T.params[i];
    if (i == T.hd->huskModel) continue;
    float dy = P->seatData ? P->seat[1] + M->lift - 0.499f : 0.f;   // сиденье по dl: y; якорь x/z — ниже, печатается dy = dy < -.3f ? -.3f : dy > .8f ? .8f : dy;
    float head = 0.46f + dy + 1.416f, k = head / M->bodyHi; n++;
    float lowCut = fminf(.65f * M->bodyHi, 2.0f);   // высокий кузов (грузовик с будкой 5 м): ориентир — кабина ~2 м
    int ok = head >= lowCut;                           // «тонет»: макушка ниже ориентира — нарушение
    const char *hi = k > 1.10f ? " ВЫШЕ КУЗОВА (открытая/необычная машина, глазами)" : "";
    printf("%s %.16s: сиденье %s %.3f, якорь %.2f;%.2f, дверь %.2f, макушка %.2f м = %.0f %% кузова (%.2f м)%s\n", ok ? "ok  " : "FAIL", M->name, P->seatData ? "dl" : "запасное", P->seat[1] + M->lift, P->seatAx, P->seatAz, P->doorX, head, k * 100.f, M->bodyHi, hi);
    bad += !ok;
    // №666: запечённый водитель (owner 4): у ИИ-машины рисуется, у машины игрока (trHideDriver) — нет
    Car ck; memset(&ck, 0, sizeof ck); ck.y = 1.f;
    trHideDriver = 0; nDrv = nAll = 0; trafficDrawModel(M, T.piece, T.vert, &ck, 0.f, 0, fn, 0, 0); int ai = nDrv, all = nAll;
    trHideDriver = 1; nDrv = nAll = 0; trafficDrawModel(M, T.piece, T.vert, &ck, 0.f, 0, fn, 0, 0); int pl = nDrv, allPl = nAll;
    trHideDriver = 0;
    int dok = pl == 0 && allPl == all - ai;   // у модели может не быть запечённого водителя (ai 0): тогда ничего не прячется
    printf("%s %.16s: водитель-кусков у ИИ %d, у игрока %d (всего кусков %d -> %d)\n", dok ? "ok  " : "FAIL", M->name, ai, pl, all, allPl);
    bad += !dok; withDrv += ai > 0;
  }
  if (!withDrv) { printf("FAIL: ни у одной модели нет куска водителя (owner 4) — пакет экспортирован с TRF_DRIVER_OLD или старым экспортёром\n"); bad++; }
  printf("моделей %d, с запечённым водителем %d, нарушений %d\n", n, withDrv, bad);
  return bad || !n;
}
