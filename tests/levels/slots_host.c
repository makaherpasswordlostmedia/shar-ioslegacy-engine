// Слоты рисунка стейтпропов больше 32 (tests/levels/slots.sh): подсекция SPR1 -> viewer/stateprops.c (тот же код, что EBOOT).
// Для каждого типа — экземпляр, каждое состояние (spEnter) и каждый слот: включён ли он в маске состояния (spSlotOn); слоты
// кусков и билбордов — как их читает движок. Строки:
//   T тип слотов_в_движке кусков билбордов состояний     P тип кусок слот     B тип билборд слот     S тип состояние биты
//   cc -std=c11 -I viewer tests/levels/slots_host.c viewer/stateprops.c viewer/col.c viewer/props.c viewer/coins.c viewer/car.c -lm
//   slots_host SPR1.bin                  подсекция целиком (tests/levels/slots_check.py --make)
//   slots_host --pack level.shr|collect  SPR1 из пакета уровня (PRP2 @32) или CLT1 (@20): только разбор + число широких типов
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "stateprops.h"

static unsigned char *readAll(const char *p, long *n) {
  FILE *f = fopen(p, "rb"); if (!f) return 0;
  fseek(f, 0, SEEK_END); *n = ftell(f); rewind(f);
  unsigned char *b = aligned_alloc(16, ((size_t)*n + 15) & ~(size_t)15);
  if (!b || fread(b, 1, (size_t)*n, f) != (size_t)*n) { fclose(f); return 0; }
  fclose(f); return b;
}
static unsigned u32(const unsigned char *b) { unsigned v; memcpy(&v, b, 4); return v; }

int main(int argc, char **argv) {
  if (argc < 2) { puts("usage: slots_host SPR1.bin | --pack FILE"); return 2; }
  int pack = !strcmp(argv[1], "--pack"); long n; unsigned char *b = readAll(argv[pack ? 2 : 1], &n);
  if (!b) { puts("нет файла"); return 2; }
  const unsigned char *spr = b; unsigned size = (unsigned)n;
  if (pack) {
    if (!memcmp(b, "SHR7", 4)) { unsigned po = u32(b + 96); spr = b + po + u32(b + po + 32); size = u32(b + po + 36); }
    else if (!memcmp(b, "CLT1", 4)) { spr = b + u32(b + 20); size = u32(b + 24); }
    else { puts("не SHR7/CLT1"); return 2; }
    unsigned char *a = aligned_alloc(16, (size + 15) & ~15u); memcpy(a, spr, size); spr = a;
  }
  StateProps sp; int e = spInit(&sp, spr, size);
  if (e) { printf("spInit %d\n", e); return 1; }
  unsigned wide = 0, maxcap = 0;
  for (unsigned t = 0; t < sp.ntype; t++) { unsigned c = spSlotCount(&sp, t); if (c > 32) wide++; if (c > maxcap) maxcap = c; }
  printf("SPR1 типов %u, экземпляров %u, типов шире 32 слотов %u, наибольшая ёмкость %u\n", sp.ntype, sp.ninst, wide, maxcap);
  if (pack) return 0;
  for (unsigned t = 0; t < sp.ntype; t++) {
    const SpType *T = &sp.type[t]; unsigned cap = spSlotCount(&sp, t);
    printf("T %u %u %u %u %u\n", t, cap, T->nPiece, T->nBill, T->nState);
    for (unsigned k = 0; k < T->nPiece; k++) printf("P %u %u %u\n", t, k, ((unsigned)sp.piece[T->firstPiece + k].flags >> 16) & 0xFF);
    for (unsigned k = 0; k < T->nBill; k++) printf("B %u %u %u\n", t, k, sp.bill[T->firstBill + k].slot);
    int inst = -1; for (unsigned i = 0; i < sp.ninst; i++) if (sp.inst[i].type == t) { inst = (int)i; break; }
    if (inst < 0) continue;
    for (unsigned s = 0; s < T->nState; s++) {
      spEnter(&sp, (unsigned)inst, (int)s);
      printf("S %u %u ", t, s);
      for (unsigned k = 0; k < cap; k++) putchar(spSlotOn(&sp, (unsigned)inst, k) ? '1' : '0');
      putchar('\n');
    }
  }
  spFree(&sp); return 0;
}
