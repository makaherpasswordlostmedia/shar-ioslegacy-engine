// Звук миссий в игре без экрана (tools/bots): таблица дорожек music.sap (имя, длина) и событий музыки MEVT из sfx.sab —
// те же файлы, что у EBOOT (tools/sound_export.py). Звука нет: реплика «звучит» ровно свою длину по часам кадров (1/60 с),
// поэтому разговор миссии длится столько же, сколько на PSP. Строки журнала (VOICE ..., MUSIC ...) — в stdout с префиксом
// "A\t", если BW_AUDIO_LOG=1 (гейт tests/missions/voice_gate.sh); иначе молча.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "msn_audio_host.h"

typedef struct { char name[28]; float sec; } HTrack;
typedef struct { char event[28]; short track[3]; unsigned char n, kind; } HMEvt;
static HTrack *trk; static int ntrk;
static HMEvt *mev; static int nmev;
static int logOn; static unsigned rng = 0x9E3779B9u;

static unsigned char *readAll(const char *p, long *n) {
  FILE *f = fopen(p, "rb"); if (!f) return 0;
  fseek(f, 0, SEEK_END); *n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *b = malloc((size_t)*n); if (b && fread(b, 1, (size_t)*n, f) != (size_t)*n) { free(b); b = 0; }
  fclose(f); return b;
}
static int hTrack(void *u, const char *name) { (void)u; for (int i = 0; i < ntrk; i++) if (!strncmp(trk[i].name, name, 28)) return i; return -1; }
static float hSec(void *u, int t) { (void)u; return t >= 0 && t < ntrk ? trk[t].sec : 0.f; }
static int hMusic(void *u, const char *ev, const char **name) {
  (void)u;
  for (int i = 0; i < nmev; i++) {
    if (strncmp(mev[i].event, ev, 28)) continue;
    if (!mev[i].n) return 0;
    rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
    int t = mev[i].track[mev[i].n > 1 ? (int)(rng % mev[i].n) : 0];
    if (t < 0 || t >= ntrk) return 0;
    *name = trk[t].name; return 1;
  }
  return -1;
}
static void hLog(void *u, const char *s) { (void)u; if (logOn) { fputs("A\t", stdout); fputs(s, stdout); } }
static const MsnAudioBackend B = {0, hTrack, hSec, 0, 0, hMusic, 0, 0, hLog, 1};

int msnAudioHostLoad(const char *dir) {
  char p[600]; long n = 0; unsigned char *b;
  logOn = getenv("BW_AUDIO_LOG") != 0;
  snprintf(p, sizeof p, "%smusic.sap", dir);
  if (!(b = readAll(p, &n)) || n < 64 || memcmp(b, "SAP1", 4)) { free(b); return -1; }
  unsigned nt = *(unsigned *)(b + 8), to = *(unsigned *)(b + 12);
  if ((long)to + (long)nt * 64 > n) { free(b); return -1; }
  trk = calloc(nt ? nt : 1, sizeof *trk); ntrk = (int)nt;
  for (unsigned i = 0; i < nt; i++) {
    const unsigned char *r = b + to + i * 64;
    memcpy(trk[i].name, r, 28); trk[i].name[27] = 0;
    unsigned nsamp = *(const unsigned *)(r + 36); unsigned short rate = *(const unsigned short *)(r + 48);
    trk[i].sec = rate ? nsamp / (float)rate : 0.f;
  }
  free(b);
  snprintf(p, sizeof p, "%ssfx.sab", dir);
  if ((b = readAll(p, &n)) && n > 96 && !memcmp(b, "SAB1", 4)) {
    unsigned eo = *(unsigned *)(b + 80), el = *(unsigned *)(b + 84);
    if (eo && (long)eo + el <= n && el >= 8 && !memcmp(b + eo, "SXT1", 4)) {
      const unsigned char *e = b + eo; unsigned ns = *(const unsigned *)(e + 4);
      for (unsigned i = 0; i < ns && 8 + i * 16 + 16 <= el; i++) {
        const unsigned char *s = e + 8 + i * 16;
        unsigned off = *(const unsigned *)(s + 4), cnt = *(const unsigned *)(s + 8), st = *(const unsigned *)(s + 12);
        if (!memcmp(s, "MEVT", 4) && st == sizeof(HMEvt) && off + cnt * st <= el) {
          mev = malloc(cnt * st + 1); memcpy(mev, e + off, cnt * st); nmev = (int)cnt;
        }
      }
    }
  }
  free(b);
  return 0;
}
const MsnAudioBackend *msnAudioHostBackend(void) { return ntrk ? &B : 0; }
