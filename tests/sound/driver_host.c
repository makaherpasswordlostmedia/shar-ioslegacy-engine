#include <stdio.h>
#include <string.h>
#include "sound.h"
#include "audio.h"

int main(int argc, char **argv) {
  if (argc != 3 || sndInit(argv[1]) < 0) return 2;
  short samples[1024];
  const int events[] = {SND_SAY_BCRASH, SND_SAY_DAMAGE};
  char code[16]; snprintf(code, sizeof code, "_%s_", argv[2]);
  for (int e = 0; e < 2; e++) {
    if (!sndSay(events[e], 1) || !strstr(sndSayLastName(), code)) {
      printf("FAIL driver=%s event=%d line=%s\n", argv[2], events[e], sndSayLastName()); return 1;
    }
    for (int i = 0; i < 1500; i++) {
      sndFrame(512.f / 44100.f, 0, 2, -5, 0, 1, 0, 0, 0); audioHostMix(samples, 512);
    }
  }
  printf("PASS driver=%s: collision and damage use this driver's lines\n", argv[2]);
  sndShutdown(); return 0;
}
