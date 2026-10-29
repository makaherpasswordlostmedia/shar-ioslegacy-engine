// Учёт шести счетов раз в секунду для автотура «ИГРОК» (слово дирижёра 16.10: «в режиме игрока тур сам говорит, куда уходит кадр»).
// Строка ACCT раз в секунду копится в буфере ОЗУ, на карту (acct.txt рядом с EBOOT) пишет отдельный поток пачкой, не главный и не в кадре.
// Счета: B построение (CPU кадра, ждём GE, вызовы, ктрис, привязки) · L подгрузка (очередь клеток, загрузчик занят, видимые недогруженные,
// выгрузки, дальность; строку Загрузки2 кладёт acctSetLoad) · D делегирование (доля процессора потоков a/b/c/d/e, как cpu в ящике) · M ME (город:
// успел/отдано/сэкономлено, отказы) · S свет и тени (строку Камеры кладёт acctSetLight) · H куча (свободно, крупнейший блок).
// Цена учёта: на кадр — 7 сложений; на секунду — измеряется (acct_us в следующей строке). Включение: сценарий (smkOn) или файл acct рядом с EBOOT; файл acctoff — выкл.
#ifndef ACCT_H
#define ACCT_H
#define ACCT_BUF 16384
static char acctBuf[2][ACCT_BUF]; static volatile unsigned acctN[2]; static volatile int acctCur, acctPendBuf = -1, acctOn, acctExit;
static SceUID acctSema = -1, acctTh = -1; static char acctPath[272];
static char acctLoadS[96], acctLightS[96]; static unsigned acctUs, acctUsMax, acctUsSum, acctSecs, acctWriteN, acctDropped;
static double aW, aC, aG; static float aWmax; static long aTris, aDraws, aBinds; static unsigned aCalls, aFr, aMissMax;
void acctSetLoad(const char *s) { snprintf(acctLoadS, sizeof acctLoadS, "%s", s ? s : ""); }   // Загрузка2: «rd_ms=… late_tex=…», пробелы внутри — «_»
void acctSetLight(const char *s) { snprintf(acctLightS, sizeof acctLightS, "%s", s ? s : ""); }   // Камера: «quads=… us=…»
static int acctThread(SceSize a, void *b) {
  (void)a; (void)b;
  for (;;) {
    sceKernelWaitSema(acctSema, 1, NULL);
    int k = acctPendBuf; if (k >= 0) {
      SceUID f = sceIoOpen(acctPath, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_APPEND, 0777);
      if (f >= 0) { sceIoWrite(f, acctBuf[k], acctN[k]); sceIoClose(f); acctWriteN++; }
      acctN[k] = 0; acctPendBuf = -1; }
    if (acctExit) return 0;
  }
}
static void acctInit(void) {
  char fn[256]; SceIoStat st;
  sibling(fn, "acctoff"); if (sceIoGetstat(fn, &st) >= 0) return;
  sibling(fn, "acct"); acctOn = smkOn || sceIoGetstat(fn, &st) >= 0;
  if (!acctOn) return;
  sibling(acctPath, "acct.txt");
  { SceUID f = sceIoOpen(acctPath, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777); if (f >= 0) sceIoClose(f); }
  acctSema = sceKernelCreateSema("acct", 0, 0, 255, NULL);
  acctTh = sceKernelCreateThread("acct", acctThread, 0x50, 4096, 0, NULL);   // приоритет ниже игры: пишет в паузах
  if (acctTh >= 0) sceKernelStartThread(acctTh, 0, NULL);
  else acctOn = 0;
}
static void acctKick(void) {   // отдать заполненный буфер потоку; пока он пишет прошлый — копим дальше в текущем (при переполнении строки теряются: acctDropped)
  if (acctPendBuf >= 0 || !acctN[acctCur]) return;
  acctPendBuf = acctCur; acctCur ^= 1; acctN[acctCur] = 0; sceKernelSignalSema(acctSema, 1);
}
static void acctFlushNow(void) {   // выход сценария: дописать всё синхронно (не из кадра игрока)
  if (!acctOn) return;
  for (int i = 0; i < 100 && acctPendBuf >= 0; i++) sceKernelDelayThread(5000);
  for (int k = 0; k < 2; k++) if (acctN[k]) { SceUID f = sceIoOpen(acctPath, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_APPEND, 0777);
    if (f >= 0) { sceIoWrite(f, acctBuf[k], acctN[k]); sceIoClose(f); } acctN[k] = 0; }
  char s[96]; unsigned n = (unsigned)snprintf(s, sizeof s, "ACCTCOST secs=%u us_avg=%u us_max=%u writes=%u dropped=%u\n", acctSecs, acctSecs ? acctUsSum / acctSecs : 0, acctUsMax, acctWriteN, acctDropped);
  SceUID f = sceIoOpen(acctPath, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_APPEND, 0777); if (f >= 0) { sceIoWrite(f, s, n); sceIoClose(f); }
}
static inline void acctFrame(float work, float cpu, float ge, long tris, int draws, int binds, unsigned calls) {
  aW += work; aC += cpu; aG += ge; if (work > aWmax) aWmax = work; aTris += tris; aDraws += draws; aBinds += binds; aCalls += calls; aFr++;
  if (stMissNow > (int)aMissMax) aMissMax = (unsigned)stMissNow;
}
static void acctSecond(const char *place) {
  if (!acctOn || !aFr) return;
  unsigned t0 = sceKernelGetSystemTimeLow(); double k = 1.0 / aFr;
  char *p = acctBuf[acctCur] + acctN[acctCur]; unsigned room = ACCT_BUF - acctN[acctCur];
  if (room < 480) { acctDropped++; acctKick(); aW = aC = aG = 0; aWmax = 0; aTris = aDraws = aBinds = 0; aCalls = aFr = aMissMax = 0; return; }
  float heap = smokeHeapFree(), blk = memMaxBlockMB();
  int n = snprintf(p, room, "ACCT t=%.1f sc=%s pl=%s | B fr=%u w=%.2f wmax=%.2f cpu=%.2f ge=%.2f calls=%.0f kt=%.1f draws=%.0f binds=%.0f | L lq=%d busy=%d late=%u dd=%.0f loads=%u bad=%u %s | D %u/%u/%u/%u/%u | M %s | S %s | H free=%.2f blk=%.2f | acct_us=%u\n",
                   smkT, smkScene, place, aFr, aW * k, aWmax, aC * k, aG * k, aCalls * k, aTris * k / 1000.0, aDraws * k, aBinds * k,
                   lqn, loaderBusy, aMissMax, drawDist, stLoads, smkGeBad - smkGeBad0, acctLoadS, bbThPct[0], bbThPct[1], bbThPct[2], bbThPct[3], bbThPct[4],
                   ccAcct, acctLightS, heap, blk, acctUs);
  if (n > 0 && (unsigned)n < room) acctN[acctCur] += (unsigned)n;
  aW = aC = aG = 0; aWmax = 0; aTris = aDraws = aBinds = 0; aCalls = aFr = aMissMax = 0;
  acctSecs++; if (acctSecs % 8 == 0 || acctN[acctCur] > ACCT_BUF / 2) acctKick();
  acctUs = sceKernelGetSystemTimeLow() - t0; acctUsSum += acctUs; if (acctUs > acctUsMax) acctUsMax = acctUs;
}
#endif
