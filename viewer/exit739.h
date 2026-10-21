// №739: просьба выйти из игры из чужого потока (HOME, конец тура) — исполняет главный поток (exitSafeNow, main_loop.h)
#ifndef SHAR_EXIT739_H
#define SHAR_EXIT739_H
#include <pspkernel.h>
#ifndef EXIT739_OLD
#define EXIT739_OLD 0   // №739 (PSP намертво висла на выходе: система звалась из чужого потока, а смеситель звука, чтение музыки и загрузчик клеток работали
                        // дальше — 5 выходов чистые, 6-й повис): HOME и конец тура только просят выход (exitReq); главный поток на ближайшем кадре гасит звук,
                        // дожидается тишины загрузчика и зовёт систему (exitSafeNow, main_loop.h). Главный поток не ответил за EXIT_FALLBACK_US — система напрямую,
                        // как раньше (выход не теряется). 1 — прежнее: система сразу из потока обратного вызова
#endif
#define EXIT_FALLBACK_US 3000000u
static volatile int exitReq;   // №739: просьба выйти (HOME, конец тура) — исполняет главный поток
static void exitRequestWait(void) {   // из чужого потока: попросить и подождать главный; не дождались — выход напрямую
  exitReq = 1;
  for (unsigned waited = 0; waited < EXIT_FALLBACK_US; waited += 20000) sceKernelDelayThread(20000);
  sceKernelExitGame();
}
#endif
