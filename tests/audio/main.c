// SHAR audio test EBOOT: plays the level-1 music, rev the family car engine, horn, skid, crashes, every effect
// of the pack. Uses viewer/audio.c unchanged. Pack: "audio/" folder next to EBOOT.PBP (sfx.sab + music.sap).
// Controls:  X / stick up = gas   [] = brake / reverse   O = horn (hold)   L = skid (hold, +R = dirt)
//            R = crash (random size)   /\ = next music track   SELECT = queue next track at the loop end
//            left/right = choose effect, up = play it, down = ambience on/off, START = music on/off
// A file named "autotest" next to EBOOT.PBP runs a 20 s scripted test (silent), writes audiotest.txt and exits.
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspdebug.h>
#include <pspctrl.h>
#include <psppower.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "audio.h"

PSP_MODULE_INFO("SHARAUDIO", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(-1024);

static int exitCb(int a, int b, void *c) { sceKernelExitGame(); return 0; }
static int cbThread(SceSize a, void *b) {
  int id = sceKernelCreateCallback("exit", exitCb, NULL);
  sceKernelRegisterExitCallback(id); sceKernelSleepThreadCB(); return 0;
}

static char base[256];
static void sibling(char *out, const char *name) { snprintf(out, 256, "%s%s", base, name); }

#define LINE(y, ...) do { char _b[320]; snprintf(_b, sizeof _b, __VA_ARGS__); pspDebugScreenSetXY(0, y); \
  pspDebugScreenPrintf("%-66.66s", _b); } while (0)

int main(int argc, char **argv) {
  int th = sceKernelCreateThread("cb", cbThread, 0x11, 0xFA0, 0, 0);
  if (th >= 0) sceKernelStartThread(th, 0, 0);
  scePowerSetClockFrequency(333, 333, 166);
  pspDebugScreenInit();
  strncpy(base, argc > 0 ? argv[0] : "", sizeof base - 32); base[sizeof base - 32] = 0;
  char *sl = strrchr(base, '/'); if (sl) sl[1] = 0; else base[0] = 0;
  static char dir[256], fn[256]; sibling(dir, "audio/");
  sibling(fn, "autotest");
  int autotest = 0; { SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f >= 0) { sceIoClose(f); autotest = 1; } }

  pspDebugScreenPrintf("SHAR audio test - loading %s\n", dir);
  unsigned t0 = sceKernelGetSystemTimeLow();
  int r = audioInit(dir);
  unsigned initMs = (sceKernelGetSystemTimeLow() - t0) / 1000;
  if (r < 0) {
    pspDebugScreenPrintf("\naudioInit failed: %s\nPut sfx.sab and music.sap into %s\nHOME to exit.", audioError(), dir);
    sceKernelSleepThread();
  }
  if (autotest) audioMaster(0);          // silent in the emulator: PPSSPP on this Mac is shared
  int ntr = audioTrackCount(), nsnd = audioSoundCount();
  int music = audioTrack("sunday_drive_intro"), amb = audioTrack("amb_suburb_day");
  int crash[3] = {audioFind("small_car_crash"), audioFind("medium_car_crash"), audioFind("large_car_crash")};
  audioMusic(music, 0); audioAmbience(amb, 0);
  int ambOn = 1, musicOn = 1, sel = 0, frame = 0, crashes = 0, played = 0;
  float v = 0, top = 120, rev = 0;
  unsigned prev = 0;
  SceCtrlData pad;
  sceCtrlSetSamplingCycle(0); sceCtrlSetSamplingMode(PSP_CTRL_MODE_ANALOG);
  // autotest log: one line per second
  static char log[8192]; int logn = 0; float cpuMax = 0, usMax = 0; int voicesMax = 0, fillMin = 100;
  logn += snprintf(log + logn, sizeof log - logn, "SHAR audio autotest  init %u ms  sounds %d tracks %d  %s\n"
                   "t_s  cpu%%  mix_us  mix_us_max  voices  music_fill%%  amb_fill%%  underruns  gear  pitch  track\n",
                   initMs, nsnd, ntr, audioError());
  for (;;) {
    sceDisplayWaitVblankStart();
    frame++;
    float t = frame / 60.f, dt = 1 / 60.f;
    sceCtrlPeekBufferPositive(&pad, 1);
    unsigned b = pad.Buttons, hit = b & ~prev; prev = b;
    float thr = (b & PSP_CTRL_CROSS) ? 1.f : pad.Ly < 60 ? (60 - pad.Ly) / 60.f : 0.f;
    int brake = (b & PSP_CTRL_SQUARE) != 0, horn = (b & PSP_CTRL_CIRCLE) != 0;
    float skid = (b & PSP_CTRL_LTRIGGER) ? 0.8f : 0.f; int dirt = (b & PSP_CTRL_RTRIGGER) && skid > 0;
    if (autotest) {                      // scripted: gears up, coast, horn, crash, skid, brake, reverse, effects
      thr = (t > 1 && t < 8) ? 1.f : 0.f; brake = t > 12.5f && t < 16; horn = t > 8.5f && t < 9.3f;
      skid = (t > 10 && t < 11) ? 0.8f : 0.f; dirt = t > 10.5f;
      if (t > 9.5f && !crashes) { audioPlay(crash[1], 1, 0.3f, 1); crashes = 1; }
      if (frame == 11 * 60) audioMusic(audioTrack("collection02_pickup"), 0.5f);
      if (frame == 12 * 60) audioMusicNext(audioTrack("sunday_drive_end_sus1"));
      if (t > 16 && t < 19.5f && frame % 6 == 0 && played < nsnd) {
        int h = audioPlay(played, 0.8f, (played % 3 - 1) * 0.5f, 1); played++;
        if (h && (played & 1)) audioStop(h);   // half of them stopped at once: exercises the stop path
      }
    }
    if (brake && v <= 0.5f) { rev = 1; } if (thr > 0 && !brake) rev = 0;
    if (rev && brake) v = v > -25 ? v - 20 * dt : v;
    else if (brake) v = v > 0 ? v - 70 * dt : 0;
    else v += (thr * 22.f * (1 - v / top) - (v > 0 ? 3.f : v < 0 ? -3.f : 0)) * dt;
    if (!brake && !thr && fabsf(v) < 0.5f) v = 0;
    audioEngine(v, top, rev && brake ? 0.6f : thr, AUDIO_ENGINE_ON | (v < 0 ? AUDIO_ENGINE_REVERSE : 0));
    audioHorn(horn);
    audioSkid(skid, dirt);
    if (hit & PSP_CTRL_RTRIGGER && !skid) audioPlay(crash[frame % 3], 1, 0, 1);
    if (hit & PSP_CTRL_TRIANGLE && ntr) {
      music = (music + 1) % ntr;
      if (!strncmp(audioTrackName(music), "amb_", 4)) music = 0;
      audioMusic(music, 0.5f); musicOn = 1;
    }
    if (hit & PSP_CTRL_SELECT && ntr) audioMusicNext((music + 1) % ntr);
    if (hit & PSP_CTRL_START) { musicOn = !musicOn; audioMusic(musicOn ? music : -1, 0.5f); }
    if (hit & PSP_CTRL_DOWN) { ambOn = !ambOn; audioAmbience(ambOn ? amb : -1, 1.f); }
    if (hit & PSP_CTRL_RIGHT) sel = (sel + 1) % (nsnd ? nsnd : 1);
    if (hit & PSP_CTRL_LEFT) sel = (sel + nsnd - 1) % (nsnd ? nsnd : 1);
    if (hit & PSP_CTRL_UP) audioPlay(sel, 1, 0, 1);

    AudioStats s; audioStats(&s);
    if (s.cpu > cpuMax) cpuMax = s.cpu;
    if (s.mixUsMax > usMax) usMax = s.mixUsMax;
    if (s.voices > voicesMax) voicesMax = s.voices;
    if (t > 2 && s.track[0] >= 0 && s.fill[0] < fillMin) fillMin = s.fill[0];
    if (autotest && frame % 60 == 0 && logn < (int)sizeof log - 200)
      logn += snprintf(log + logn, sizeof log - logn, "%4.0f  %4.1f  %6.0f  %10.0f  %6d  %11d  %9d  %9d  %4d  %5.2f  %s\n",
                       t, s.cpu, s.mixUs, s.mixUsMax, s.voices, s.fill[0], s.fill[1], s.underruns, s.gear, s.enginePitch,
                       s.track[0] >= 0 ? audioTrackName(s.track[0]) : "-");
    if (frame % 6 == 0) {
      LINE(0, "SHAR audio test  (%s)%s", dir, autotest ? "  AUTOTEST, silent" : "");
      LINE(2, "Audio thread CPU %4.1f %%   mix %4.0f us / 11610 us, worst %4.0f us", s.cpu, s.mixUs, s.mixUsMax);
      LINE(3, "Voices %2d  underruns %d  dropped %d  limiter %.2f  IO max %d ms", s.voices, s.underruns, s.dropped,
           s.limiter, s.ioMaxMs);
      LINE(5, "Music    %-22s %6.1f s  buffer %3d%%", s.track[0] >= 0 ? audioTrackName(s.track[0]) : "(stopped)",
           s.trackPos[0], s.fill[0]);
      LINE(6, "Ambience %-22s %6.1f s  buffer %3d%%", s.track[1] >= 0 ? audioTrackName(s.track[1]) : "(off)",
           s.trackPos[1], s.fill[1]);
      LINE(8, "Car famil_v  %5.1f km/h  gear %2d  pitch %.2f  engine vol %.2f", v, s.gear, s.enginePitch, s.engineVol);
      LINE(9, "gas %.2f  %s%s%s", thr, horn ? "HORN " : "", skid > 0 ? (dirt ? "DIRT-SKID " : "SKID ") : "",
           v < 0 ? "REVERSE" : "");
      LINE(11, "Effect %3d/%d: %s", sel + 1, nsnd, audioSoundName(sel));
      LINE(13, "X/stick gas  [] brake/reverse  O horn  L skid (+R dirt)  R crash");
      LINE(14, "/\\ next track  SELECT next at loop end  START music  v ambience");
      LINE(15, "<- -> choose effect   ^ play effect");
      LINE(17, "pack: %d sounds, %d tracks, init %u ms", nsnd, ntr, initMs);
    }
    if (autotest && t >= 20.f) {
      logn += snprintf(log + logn, sizeof log - logn,
                       "summary: cpu max %.1f %%  mix worst %.0f us of 11610  voices max %d  music buffer min %d %%  "
                       "underruns %d  dropped %d  limiter buffers %u  io max %d ms  io bytes %u  effects played %d\n"
                       "note: PPSSPP timing is not PSP timing\n",
                       cpuMax, usMax, voicesMax, fillMin, s.underruns, s.dropped, s.limiterBuffers, s.ioMaxMs, s.ioBytes, played);
      sibling(fn, "audiotest.txt");
      SceUID f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777);
      if (f >= 0) { sceIoWrite(f, log, logn); sceIoClose(f); }
      LINE(19, "AUTOTEST DONE -> audiotest.txt");
      sceKernelDelayThread(1500000);
      audioShutdown();
      sceKernelExitGame();
    }
  }
  return 0;
}
