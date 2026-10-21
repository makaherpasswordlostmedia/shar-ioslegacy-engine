// Правки 269/273/276, ступень 0: задание пробы Media Engine на Маке — та же функция meJobSum (viewer/me/mebox.h), что считает
// ME и главный процессор PSP (правило конвейера ME: одна функция, сверка бит в бит). Печать: «job K SUM» для заданий 1..100 и
// «stale K SUM» — сумма задания K, если одна строка кэша (16 слов) осталась от задания K-1 (так выглядит забытый сброс кэша).
// cc -O2 -o sum_test tests/me/sum_test.c && ./sum_test   (сверку с независимым подсчётом делает tests/me/run.py)
#include <stdio.h>
#include "../../viewer/me/mebox.h"
static unsigned buf[ME_PROBE_WORDS];
int main(void) {
  for (unsigned k = 1; k <= ME_PROBE_JOBS; k++) {
    for (unsigned i = 0; i < ME_PROBE_WORDS; i++) buf[i] = meJobWord(k, i);
    printf("job %u %08x\n", k, meJobSum(buf, ME_PROBE_WORDS));
    if (k > 1) { for (unsigned i = 1024; i < 1040; i++) buf[i] = meJobWord(k - 1, i); printf("stale %u %08x\n", k, meJobSum(buf, ME_PROBE_WORDS)); }
  }
  return 0;
}
