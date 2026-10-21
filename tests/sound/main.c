// SHAR sound test EBOOT (stage 6): runs tests/sound/scenario.h through viewer/sound.c + viewer/audio.c.
// Pack: folder "audio/" next to EBOOT.PBP (sfx.sab + music.sap from tools/sound_export.py).
// Normal run: plays the 44 s scenario with sound, shows mixer CPU / voices / streams; START = run again.
// File "autotest" next to EBOOT.PBP: speakers muted (the Mac's PPSSPP is shared), the mixed output is captured
// to capture.wav, a per-second log goes to soundtest.txt, then "done" is written and the EBOOT exits.
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspdebug.h>
#include <pspctrl.h>
#include <psppower.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "scenario.h"

PSP_MODULE_INFO("SHARSOUND", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(-1024);

static int exitCb(int a, int b, void *c) { sceKernelExitGame(); return 0; }
static int cbThread(SceSize a, void *b) {
  int id = sceKernelCreateCallback("exit", exitCb, NULL);
  sceKernelRegisterExitCallback(id); sceKernelSleepThreadCB(); return 0;
}
static char base[256];
static void sibling(char *out, const char *name) { snprintf(out, 256, "%s%s", base, name); }
static void writeFile(const char *name, const void *a, int na, const void *b, int nb) {
  char fn[256]; sibling(fn, name);
  SceUID f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777);
  if (f < 0) return;
  if (na) sceIoWrite(f, a, na);
  if (nb) sceIoWrite(f, b, nb);
  sceIoClose(f);
}
#define LINE(y, ...) do { char _b[320]; snprintf(_b, sizeof _b, __VA_ARGS__); pspDebugScreenSetXY(0, y); \
  pspDebugScreenPrintf("%-66.66s", _b); } while (0)

int main(int argc, char **argv) {
  int th = sceKernelCreateThread("cb", cbThread, 0x11, 0xFA0, 0, 0);
  if (th >= 0) sceKernelStartThread(th, 0, 0);
  scePowerSetClockFrequency(333, 333, 166);
  pspDebugScreenInit();
  strncpy(base, argc > 0 ? argv[0] : "", sizeof base - 32); base[sizeof base - 32] = 0;
  char *sl = strrchr(base, '/'); if (sl) sl[1] = 0; else base[0] = 0;
  static char dir[256], fn[256]; sibling(dir, "audio/"); sibling(fn, "autotest");
  int autotest = 0; { SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f >= 0) { sceIoClose(f); autotest = 1; } }
  pspDebugScreenPrintf("SHAR sound test - loading %s\n", dir);
  unsigned t0 = sceKernelGetSystemTimeLow();
  int r = sndInit(dir);
  unsigned initMs = (sceKernelGetSystemTimeLow() - t0) / 1000;
  static char log[16384]; int logn = 0;
  if (r < 0) {
    logn = snprintf(log, sizeof log, "sndInit failed: %s\n", sndError());
    if (autotest) { writeFile("soundtest.txt", log, logn, 0, 0); writeFile("done", "1", 1, 0, 0); sceKernelExitGame(); }
    pspDebugScreenPrintf("\n%sPut sfx.sab and music.sap into %s\nHOME to exit.", log, dir);
    sceKernelSleepThread();
  }
  short *cap = 0; unsigned capMax = 0;
  if (autotest) {
    audioOutputVolume(0);
    capMax = (unsigned)(SCN_END * 44100) + 44100;
    cap = malloc(capMax * 4);
    if (cap) audioCapture(cap, capMax); else capMax = 0;
  }
  logn += snprintf(log + logn, sizeof log - logn,
                   "SHAR sound autotest  init %u ms  sounds %d  tracks %d  capture %s  %s\n"
                   "t_s  mixcpu%%  mix_us  mix_us_max  voices  fill_mus/amb/dlg/pos%%  underruns  dropped  io_max_ms  "
                   "snd_us_max  gear  music | ambience | positional | dialog\n",
                   initMs, audioSoundCount(), audioTrackCount(), cap ? "on" : "off", sndError());
  Scn s; memset(&s, 0, sizeof s);
  int frame = 0; unsigned prev = 0, sndMax = 0, sndMaxAll = 0; float cpuMax = 0, usMax = 0; int voicesMax = 0;
  unsigned tStart = sceKernelGetSystemTimeLow();
  SceCtrlData pad; sceCtrlSetSamplingCycle(0);
  for (;;) {
    sceDisplayWaitVblankStart();
    frame++;
    float t = (sceKernelGetSystemTimeLow() - tStart) * 1e-6f, dt = 1 / 60.f;
    sceCtrlPeekBufferPositive(&pad, 1);
    unsigned hit = pad.Buttons & ~prev; prev = pad.Buttons;
    unsigned a0 = sceKernelGetSystemTimeLow();
    int go = scenario(&s, t, dt);
    sndFrame(dt, s.cx, s.cy, s.cz, 0.f, 1.f, s.px, s.py, s.pz);
    unsigned su = sceKernelGetSystemTimeLow() - a0;
    if (su > sndMax) sndMax = su;
    AudioStats a; audioStats(&a); SndStats st; sndStats(&st);
    if (t > 1 && a.cpu > cpuMax) cpuMax = a.cpu;
    if (t > 1 && a.mixUsMax > usMax) usMax = a.mixUsMax;
    if (a.voices > voicesMax) voicesMax = a.voices;
    if (frame % 60 == 0 && logn < (int)sizeof log - 300) {
      logn += snprintf(log + logn, sizeof log - logn, "%4.0f  %5.1f  %6.0f  %10.0f  %6d  %3d/%3d/%3d/%3d  %9d  %7d  %9d  %10u  %4d  %s | %s | %s | %s\n",
                       t, a.cpu, a.mixUs, a.mixUsMax, a.voices, a.fill[0], a.fill[1], a.fill[2], a.fill[3], a.underruns,
                       a.dropped, a.ioMaxMs, sndMax, a.gear, st.music, st.ambience, st.positional, st.dialog);
      if (sndMax > sndMaxAll) sndMaxAll = sndMax;
      sndMax = 0;
    }
    if (frame % 6 == 0) {
      LINE(0, "SHAR sound test%s   t %5.1f / %.0f s", autotest ? "  AUTOTEST (muted, capture)" : "", t, SCN_END);
      LINE(2, "Mixer thread CPU %4.1f %%   mix %4.0f us / 11610 us, worst %4.0f", a.cpu, a.mixUs, a.mixUsMax);
      LINE(3, "Voices %2d  underruns %d  dropped %d  limiter %.2f  IO max %d ms", a.voices, a.underruns, a.dropped, a.limiter, a.ioMaxMs);
      LINE(5, "Music      %-24s buf %3d%%", st.music, a.fill[0]);
      LINE(6, "Ambience   %-24s buf %3d%%", st.ambience, a.fill[1]);
      LINE(7, "Positional %-24s buf %3d%%", st.positional, a.fill[3]);
      LINE(8, "Homer      %-24s buf %3d%%", st.dialog, a.fill[2]);
      LINE(10, "Car %5.1f km/h  gear %2d  pitch %.2f  vol %.2f", s.v * 3.6f, a.gear, a.enginePitch, a.engineVol);
      LINE(11, "Effect %d / %d", s.sfx, audioSoundCount());
      LINE(13, "START = run the scenario again   HOME = exit");
    }
    if (hit & PSP_CTRL_START) { memset(&s, 0, sizeof s); tStart = sceKernelGetSystemTimeLow(); }
    if (!go && autotest) {
      AudioStats a2; audioStats(&a2);
      unsigned frames = cap ? audioCaptured() : 0;
      logn += snprintf(log + logn, sizeof log - logn,
                       "summary: mixer cpu max %.1f %% (of one 333 MHz core, 1 s windows)  mix worst %.0f us of 11610  "
                       "voices max %d  underruns %d  dropped %d  limiter buffers %u  io max %d ms  io bytes %u  "
                       "sndFrame+scenario worst %u us  effects %d  captured %.1f s\nnote: PPSSPP timing is not PSP timing\n",
                       cpuMax, usMax, voicesMax, a2.underruns, a2.dropped, a2.limiterBuffers, a2.ioMaxMs, a2.ioBytes,
                       sndMaxAll, s.sfx, frames / 44100.f);
      writeFile("soundtest.txt", log, logn, 0, 0);
      if (cap && frames) {
        unsigned char h[44]; unsigned bytes = frames * 4, v;
        memcpy(h, "RIFF", 4); v = 36 + bytes; memcpy(h + 4, &v, 4); memcpy(h + 8, "WAVEfmt ", 8);
        v = 16; memcpy(h + 16, &v, 4); unsigned short u = 1; memcpy(h + 20, &u, 2); u = 2; memcpy(h + 22, &u, 2);
        v = 44100; memcpy(h + 24, &v, 4); v = 44100 * 4; memcpy(h + 28, &v, 4); u = 4; memcpy(h + 32, &u, 2);
        u = 16; memcpy(h + 34, &u, 2); memcpy(h + 36, "data", 4); memcpy(h + 40, &bytes, 4);
        audioCapture(0, 0);
        writeFile("capture.wav", h, 44, cap, (int)bytes);
      }
      writeFile("done", "1", 1, 0, 0);
      LINE(15, "AUTOTEST DONE -> soundtest.txt, capture.wav");
      sndShutdown();
      sceKernelExitGame();
    }
  }
  return 0;
}
