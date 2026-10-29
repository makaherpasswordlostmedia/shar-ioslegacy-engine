// Mac-side harness: runs viewer/audio.c (the exact PSP mixer code, AUDIO_HOST build) without a PSP.
//   audio_host dump <packdir> <outdir>   raw renders for tools/audio_export.py verify
//   audio_host demo <packdir> <out.wav>  20 s scripted drive (engine through the gears, horn, crash, skid, music)
//   audio_host bench <packdir>           host mixing cost per buffer (for relative comparison only)
// Build: make -C tests/audio/host
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "audio.h"

#define B 512
static short buf[B * 2];
static FILE *seamf; static unsigned seamBase;
static void hook(unsigned fr) { if (seamf) fprintf(seamf, "%u\n", fr - seamBase); }

static FILE *openw(const char *dir, const char *name) {
  char p[512]; snprintf(p, sizeof p, "%s/%s", dir, name);
  FILE *f = fopen(p, "wb"); if (!f) { perror(p); exit(1); }
  return f;
}
static void mix(void) { audioHostMix(buf, B); }
static void badDump(const char *name) { fprintf(stderr, "dump incomplete: %s\n", name); exit(1); }

static void dump(const char *pack, const char *out) {
  AudioStats st;
  // 1) bit-exact: every resident file, one pass, unity gain/step
  audioTestForceUnity(1);
  int nf = audioTestFileCount();
  for (int i = 0; i < nf; i++) {
    int ch, rate; unsigned ns; audioTestFileInfo(i, &ch, &rate, &ns);
    char name[64]; snprintf(name, sizeof name, "sfx_%03d.raw", i);
    FILE *f = openw(out, name);
    audioTestPlayFile(i);
    unsigned limit = (ns + B - 1) / B + 128;
    for (unsigned guard = 0; guard < limit; guard++) {
      mix();
      for (int k = 0; k < B; k++) fwrite(&buf[k * 2], 2, ch == 2 ? 2 : 1, f);
      audioStats(&st); if (!st.voices) break;
    }
    fclose(f);
    if (st.voices) badDump(name);
  }
  // 2) bit-exact: every stream track through the ring buffer + segment queue, one pass
  int nt = audioTrackCount();
  for (int t = 0; t < nt; t++) {
    int loop, next, bus; unsigned ns, ls, le;
    audioTestTrackInfo(t, &loop, &next, &bus, &ns, &ls, &le);
    char name[64]; snprintf(name, sizeof name, "mus_%s.raw", audioTrackName(t));
    FILE *f = openw(out, name);
    audioTestMusicOnce(t);
    int started = 0;
    unsigned limit = (ns + B - 1) / B + 128;
    for (unsigned guard = 0; guard < limit; guard++) {
      mix(); audioStats(&st);
      if (!started && st.track[0] == t) started = 1;
      if (started) fwrite(buf, 4, B, f);
      if (started && st.track[0] < 0) break;
      if (!started && guard == 127) break;
    }
    fclose(f);
    if (!started || st.track[0] >= 0) badDump(name);
  }
  audioTestMusicOnce(-1);
  audioTestForceUnity(0);
  for (int b = 0; b < AUDIO_NBUS; b++) audioBus(b, 1);
  audioMaster(1);
  // 3) through the real 44.1 kHz resampler: first 3 tracks, first 3 one-shot files
  for (int t = 0; t < nt && t < 3; t++) {
    int loop, next, bus; unsigned ns, ls, le;
    audioTestTrackInfo(t, &loop, &next, &bus, &ns, &ls, &le);
    char name[64]; snprintf(name, sizeof name, "mix_%s.raw", audioTrackName(t));
    FILE *f = openw(out, name);
    audioTestMusicOnce(t);
    int started = 0;
    unsigned limit = (unsigned)(audioTrackSeconds(t) * 44100.f / B) + 128;
    for (unsigned guard = 0; guard < limit; guard++) {
      mix(); audioStats(&st);
      if (!started && st.track[0] == t) started = 1;
      if (started) fwrite(buf, 4, B, f);
      if (started && st.track[0] < 0) break;
      if (!started && guard == 127) break;
    }
    fclose(f);
    if (!started || st.track[0] >= 0) badDump(name);
  }
  audioTestMusicOnce(-1);
  for (int i = 0, done = 0; i < nf && done < 3; i++) {
    int ch, rate; unsigned ns; audioTestFileInfo(i, &ch, &rate, &ns);
    char name[64]; snprintf(name, sizeof name, "mix_sfx_%03d.raw", i);
    FILE *f = openw(out, name);
    audioTestPlayFile(i);
    unsigned limit = (unsigned)(ns * (44100.0 / rate) / B) + 128;
    for (unsigned guard = 0; guard < limit; guard++) { mix(); fwrite(buf, 4, B, f); audioStats(&st); if (!st.voices) break; }
    fclose(f); done++;
    if (st.voices) badDump(name);
  }
  // 4) loop seams through the mixer: looping resources at pitch 1.0 and 1.75, looping tracks (+ intro chain)
  audioTestSeamHook = hook;
  int nr = audioSoundCount();
  for (int id = 0; id < nr; id++) {
    if (!audioTestResLoops(id)) continue;
    for (int pi = 0; pi < 2; pi++) {
      float pitch = pi ? 1.75f : 1.f;
      char name[96]; snprintf(name, sizeof name, "loop_%s_p%03d.raw", audioSoundName(id), (int)(pitch * 100));
      FILE *f = openw(out, name);
      snprintf(name, sizeof name, "loop_%s_p%03d.seams", audioSoundName(id), (int)(pitch * 100));
      seamf = openw(out, name); seamBase = audioTestFramesOut();
      int h = audioPlay(id, 1, 0, pitch);
      int n0 = audioTestSeamCount();
      for (int guard = 0; guard < 4000 && audioTestSeamCount() - n0 < 5; guard++) { mix(); fwrite(buf, 4, B, f); }
      for (int k = 0; k < 20; k++) { mix(); fwrite(buf, 4, B, f); }
      audioStop(h); mix(); mix();
      fclose(f); fclose(seamf); seamf = 0;
    }
  }
  for (int t = 0; t < nt; t++) {
    int loop, next, bus; unsigned ns, ls, le;
    audioTestTrackInfo(t, &loop, &next, &bus, &ns, &ls, &le);
    if (!loop) continue;
    int first = t;                                  // start from an intro that chains into this loop, if any
    for (int u = 0; u < nt; u++) { int l2, n2, b2; unsigned a, b_, c; audioTestTrackInfo(u, &l2, &n2, &b2, &a, &b_, &c); if (n2 == t) first = u; }
    char name[96]; snprintf(name, sizeof name, "loop_%s.raw", audioTrackName(t));
    FILE *f = openw(out, name);
    snprintf(name, sizeof name, "loop_%s.seams", audioTrackName(t));
    seamf = openw(out, name);
    int s = bus == 1 ? 1 : 0;
    if (s) audioAmbience(first, 0); else audioMusic(first, 0);
    int started = 0; unsigned want = 0, got = 0;
    for (int guard = 0; guard < 2000000; guard++) {
      mix(); audioStats(&st);
      if (!started && st.track[s] >= 0) {
        started = 1; seamBase = audioTestFramesOut() - B;
        unsigned introS = 0;
        if (first != t) { int l2, n2, b2; unsigned a, b_, c; audioTestTrackInfo(first, &l2, &n2, &b2, &a, &b_, &c); introS = a; }
        want = (unsigned)((introS + (le - ls)) * (44100.0 / 24000.0)) + 44100 * 3;   // one full pass + 3 s
      }
      if (started) { fwrite(buf, 4, B, f); got += B; if (got >= want) break; }
    }
    if (s) audioAmbience(-1, 0); else audioMusic(-1, 0);
    for (int k = 0; k < 8; k++) mix();
    fclose(f); fclose(seamf); seamf = 0;
  }
  audioTestSeamHook = 0;
  audioStats(&st);
  printf("dump done: %d files, %d tracks, underruns %d, dropped %d, seams %d\n", nf, nt, st.underruns, st.dropped,
         audioTestSeamCount());
}

static void wavHeader(FILE *f, unsigned frames) {
  unsigned bytes = frames * 4, v;
  fwrite("RIFF", 1, 4, f); v = 36 + bytes; fwrite(&v, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f);
  v = 16; fwrite(&v, 4, 1, f); unsigned short s = 1; fwrite(&s, 2, 1, f); s = 2; fwrite(&s, 2, 1, f);
  v = 44100; fwrite(&v, 4, 1, f); v = 44100 * 4; fwrite(&v, 4, 1, f); s = 4; fwrite(&s, 2, 1, f); s = 16; fwrite(&s, 2, 1, f);
  fwrite("data", 1, 4, f); fwrite(&bytes, 4, 1, f);
}

static void demo(const char *wav) {
  FILE *f = fopen(wav, "wb"); if (!f) { perror(wav); exit(1); }
  wavHeader(f, 0);
  audioMusic(audioTrack("sunday_drive_intro"), 0);
  audioAmbience(audioTrack("amb_suburb_day"), 0);
  int crash = audioFind("medium_car_crash");
  float v = 0, top = 120; unsigned frames = 0; int crashed = 0; AudioStats st;
  for (float t = 0; t < 20.f; t += B / 44100.f) {
    float thr = (t > 1 && t < 9) ? 1.f : 0.f, dt = B / 44100.f;
    unsigned fl = AUDIO_ENGINE_ON;
    if (t >= 14 && t < 15) v -= 60 * dt;                              // brake
    else if (t >= 15 && t < 17.5f) { thr = 0.6f; fl |= AUDIO_ENGINE_REVERSE; v = v > -20 ? v - 15 * dt : v; }
    else v += (thr * 22.f * (1 - v / top) - (v > 0 ? 3.f : 0)) * dt;
    if (t >= 14 && v < 0 && t < 15) v = 0;
    if (t > 17.5f) { thr = 0; v *= 0.95f; }
    audioEngine(v * 1.f, top, thr, fl);
    audioHorn(t > 10 && t < 10.8f);
    if (t > 12 && !crashed) { audioPlay(crash, 1, 0.3f, 1); crashed = 1; }
    audioSkid(t > 12.5f && t < 13.5f ? 0.8f : 0, 0);
    mix(); fwrite(buf, 4, B, f); frames += B;
    audioStats(&st);
    if (((int)(t * 44100) / B) % 43 == 0)
      printf("t %5.2f  speed %6.1f  gear %2d  pitch %.2f  env %.2f  voices %d  music %s\n", t, v, st.gear, st.enginePitch,
             st.engineVol, st.voices, st.track[0] >= 0 ? audioTrackName(st.track[0]) : "-");
  }
  fseek(f, 0, SEEK_SET); wavHeader(f, frames); fclose(f);
  printf("wrote %s (%.1f s)\n", wav, frames / 44100.f);
}

static void bench(void) {
  audioMusic(audioTrack("sunday_drive_intro"), 0);
  audioAmbience(audioTrack("amb_suburb_day"), 0);
  int ids[6] = {audioFind("skid"), audioFind("famil_horn"), audioFind("fire"), audioFind("dirt_skid"), audioFind("horn"), audioFind("car_jump")};
  for (int k = 0; k < 6; k++) audioPlay(ids[k], 0.5f, 0, 1.3f);
  audioEngine(60, 120, 1, AUDIO_ENGINE_ON);
  for (int k = 0; k < 20; k++) mix();
  AudioStats st; audioStats(&st);
  double sum = 0; int n = 2000;
  for (int k = 0; k < n; k++) { mix(); audioStats(&st); sum += st.mixUs; }
  printf("host: %d voices, %.1f us per %d-frame mix (%.3f%% of real time on this Mac)\n", st.voices, sum / n, B,
         sum / n / (B * 1e6 / 44100) * 100);
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: %s dump|demo|bench <packdir/> [out]\n", argv[0]); return 2; }
  char dir[512]; snprintf(dir, sizeof dir, "%s%s", argv[2], argv[2][strlen(argv[2]) - 1] == '/' ? "" : "/");
  if (audioInit(dir) < 0) { fprintf(stderr, "audioInit: %s\n", audioError()); return 1; }
  if (!strcmp(argv[1], "dump") && argc > 3) dump(dir, argv[3]);
  else if (!strcmp(argv[1], "demo") && argc > 3) demo(argv[3]);
  else if (!strcmp(argv[1], "bench")) bench();
  else { fprintf(stderr, "bad args\n"); return 2; }
  return 0;
}
