// Mac render of the sound test (viewer/sound.c + viewer/audio.c, AUDIO_HOST build): the same scenario as the
// PSP EBOOT, mixed by the same code, written as a 44.1 kHz stereo WAV + a per-second log. Nothing is published.
//   make -C tests/sound/host && tests/sound/host/sound_host build/audio/ OUT.wav
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../scenario.h"

static void wavHeader(FILE *f, unsigned frames) {
  unsigned bytes = frames * 4, v;
  fwrite("RIFF", 1, 4, f); v = 36 + bytes; fwrite(&v, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f);
  v = 16; fwrite(&v, 4, 1, f); unsigned short s = 1; fwrite(&s, 2, 1, f); s = 2; fwrite(&s, 2, 1, f);
  v = 44100; fwrite(&v, 4, 1, f); v = 44100 * 4; fwrite(&v, 4, 1, f); s = 4; fwrite(&s, 2, 1, f); s = 16; fwrite(&s, 2, 1, f);
  fwrite("data", 1, 4, f); fwrite(&bytes, 4, 1, f);
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: sound_host PACKDIR/ OUT.wav\n"); return 1; }
  if (sndInit(argv[1]) < 0) { fprintf(stderr, "sndInit: %s\n", sndError()); return 1; }
  FILE *f = fopen(argv[2], "wb"); if (!f) { perror(argv[2]); return 1; }
  wavHeader(f, 0);
  static short buf[512 * 2];
  Scn s; memset(&s, 0, sizeof s);
  unsigned frames = 0; float t = 0, dt = 512.f / 44100.f; int sec = -1, clipped = 0; double e = 0; int peak = 0;
  char prev[160] = "";
  for (;;) {
    int go = scenario(&s, t, dt);
    sndFrame(dt, s.cx, s.cy, s.cz, 0.f, 1.f, s.px, s.py, s.pz);
    audioHostMix(buf, 512);
    fwrite(buf, 4, 512, f); frames += 512;
    for (int i = 0; i < 1024; i++) { int a = abs(buf[i]); if (a > peak) peak = a; if (a >= 32767) clipped++; e += (double)buf[i] * buf[i]; }
    SndStats st; sndStats(&st);
    char now[160]; snprintf(now, sizeof now, "music %s | amb %s | pos %s | dialog %s", st.music, st.ambience, st.positional, st.dialog);
    if (strcmp(now, prev)) { printf("%6.2f s  %s\n", t, now); strcpy(prev, now); }
    if ((int)t != sec) {
      sec = (int)t;
      AudioStats a; audioStats(&a);
      if (sec % 4 == 0) printf("%6.2f s  voices %d  underruns %d  dropped %d  gear %d  pitch %.2f  limiter %.2f\n",
                                t, a.voices, a.underruns, a.dropped, a.gear, a.enginePitch, a.limiter);
    }
    t += dt;
    if (!go) break;
  }
  fseek(f, 0, SEEK_SET); wavHeader(f, frames); fclose(f);
  AudioStats a; audioStats(&a);
  printf("done: %.1f s, peak %d, clipped samples %d, rms %.0f, underruns %d, dropped %d, effects %d\n", frames / 44100.0,
         peak, clipped, sqrt(e / (frames * 2.0)), a.underruns, a.dropped, s.sfx);
  sndShutdown();
  return 0;
}
