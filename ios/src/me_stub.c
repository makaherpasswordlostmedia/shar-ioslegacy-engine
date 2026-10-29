/* me_stub.c - the PSP Media Engine (second MIPS core) does not exist on iOS.
 * Every ME service reports "not available", the engine falls back to its CPU paths
 * (audio mixer thread, particles on the main CPU). meprobe.c / me_gametask.c / me_math.c are not built. */
#include "psp_compat.h"
void fxSetMeMax(int n) { (void)n; }   /* viewer/fx.c defines it only for __psp__ */
unsigned meSvcDbg[4]; unsigned meSvcChained;
int meSvcScheme(void) { return 0; }
int meSvcSubmit(int c, volatile void *b, unsigned k, void *j, unsigned w) { (void)c; (void)b; (void)k; (void)j; (void)w; return -1; }
int meSvcPoll(int c, volatile void *b, unsigned s, unsigned *sum) { (void)c; (void)b; (void)s; (void)sum; return 1; }
unsigned meSvcQuiesce(void) { return 0; } void meSvcHold(int on) { (void)on; }
int meSvcHeld(void) { return 1; } int meSvcSlept(void) { return 0; } void meSvcForget(int c) { (void)c; }
int meSvcBootUser(void) { return -1; } int audioMeAttach(void) { return -1; }
int meAudioBoot(const char *d, int emu, char *r, int n) { (void)d; (void)emu; if (n > 0) snprintf(r, (size_t)n, "me: not on iOS"); return -1; }
int meProbeRun(const char *d, const char *p, int emu, char *r, int n) { (void)d; (void)p; (void)emu; if (n > 0) snprintf(r, (size_t)n, "me: not on iOS"); return -1; }
int meGameTask(int i, void *p) { (void)i; (void)p; return 0; }
int meFxBoot(const char *d, int emu, char *r, int n) { (void)d; (void)emu; if (n > 0) snprintf(r, (size_t)n, "me: not on iOS"); return -1; }
int meLadderStuck(void) { return 0; }
int meLadderRun(const char *a, int b, int c, char *r, int n) { (void)a; (void)b; (void)c; if (n > 0) r[0] = 0; return -1; }
