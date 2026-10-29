// Ревизия 11.10, 1.2: ответ sceIoPollAsync < 0 (ошибка чтения) — «закончено», слот очереди освобождается (skinPreDone). Красный контроль: -DSKINPRE_ERR_OLD=1.
#include <stdio.h>
#include "skin.h"
int main(void) {
  int bad = 0;
  if (!skinPreDone(0)) { puts("FAIL: 0 (done) not ready"); bad = 1; }
  if (skinPreDone(1)) { puts("FAIL: 1 (running) ready"); bad = 1; }
  if (!skinPreDone(-1)) { puts("FAIL: read error treated as still running forever (1.2)"); bad = 1; }
  if (!skinPreDone(-2147483647 - 1)) { puts("FAIL: large negative error"); bad = 1; }
  puts(bad ? "FAIL" : "PASS"); return bad;
}
