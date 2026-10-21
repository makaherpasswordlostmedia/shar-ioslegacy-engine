// Правка Роба 276 (пилот Media Engine, план ведущего 04.10 §3): смешивание звука — одна функция над одной структурой задания.
// Тот же код считает везде: на Маке (tests/audio/host, tests/me/run.py), в эмуляторе и на PSP главным процессором (viewer/audio.c
// mixBuffer), а с флаг-файлом meaudio — на Media Engine (модуль viewer/me/sharme.prx собирает этот же заголовок). Правила
// конвейера ME: обычная функция C без вызовов системы и библиотек (циклы вместо memcpy/memset), без глобальных переменных,
// только целые числа (FPU не нужен), вход и выход — одна структура MixJob, выровненная на 64 байта; указатель внутри — только
// MixJob.data (звуки уровня, на ME — некэшируемый адрес). Всё, что меняют другие потоки (громкость, старт/стоп, кольца музыки),
// главный процессор переносит в задание до счёта (audio.c mixPre) и забирает после (mixPost) — ME трогает только задание.
// Код перенесён из viewer/audio.c (до правки 276) без изменения счёта: декодер PS-ADPCM бит в бит с ffmpeg adpcm_psx,
// ресэмплер 16.16, усиления Q15 с линейным переходом по 32 кадра. Сверка бит в бит — tests/me/run.py, шаг «Мак, микшер».
#ifndef MIXDSP_H
#define MIXDSP_H

#define MIX_FRAMES 512                 // кадров на буфер sceAudio (11,6 мс)
#define MIX_WIN (28 * 8)               // окно декодированных сэмплов голоса
#define MIX_NVOICE 24                  // голоса звуков
#define MIX_NSTREAM 5                  // музыка, фон, речь, позиционная петля, наложение машины (= AUDIO_NSTREAM)
#define MIX_NV (MIX_NVOICE + MIX_NSTREAM)
#define MIX_NSEG 8                     // очередь кусков потока (= NSEG в audio.c)
#define MIX_SWIN 2048                  // байт кольца потока на один буфер (нужно до ~900: 512 кадров при 48 кГц + окно)
#define MIX_NSEAM 64                   // записей стыков петель на буфер (только для журнала стыков на Маке)

typedef struct { int track, rate; unsigned start, end; short hist[4]; } MixSeg;   // кусок потока; rate — из таблицы дорожек
typedef struct { int on, p[3], min, max; } MixPoint; // №390: metres Q4; max <=2048m keeps squared distance in uint32
typedef struct {
  int on, tgl, tgr; unsigned tstep;    // главный -> задание: голос звучит в этом буфере, целевые усиления Q15 и шаг 16.16
  int ch, loop, rate, stream;          // stream: -1 — звук из банка, иначе номер потока
  unsigned dataOff, loopStart, loopEnd; short lhist[4];   // звук из банка: смещение данных от MixJob.data, петля и история
  unsigned si, end; int s1[2], s2[2];  // состояние декодера (меняет только счёт)
  int bufLen; unsigned pos, step; int gl, gr;
  int finished, underrun, tail, segs;
  MixPoint point; int spatialStart;
  short buf[2][MIX_WIN + 4];
} MixVoice;
typedef struct {
  unsigned len, used, nseg, segUsed;   // байт кольца в окне / съедено; кусков в очереди / съедено
  int cur, pad[3];                     // что играет поток (меняет счёт при смене куска)
  MixSeg seg[MIX_NSEG];
  unsigned char win[MIX_SWIN];         // копия кольца с позиции чтения (блоки по 32 байта)
} MixWin;
typedef struct { int i, n; unsigned pos, step; } MixSeamRec;
typedef struct MixJob {
  const unsigned char *data;           // банк звуков уровня (на ME — адрес | 0x40000000)
  int seams, nrec, listener[3], right[2], pad[8]; // listener Q4, horizontal camera right Q15
  MixSeamRec rec[MIX_NSEAM];
  int acc[MIX_FRAMES * 2];             // выход: сумма голосов (ограничитель и громкость — на главном, audio.c mixPost)
  MixWin w[MIX_NSTREAM];
  MixVoice v[MIX_NV];
} __attribute__((aligned(64))) MixJob;

static unsigned mixSqrt(unsigned n) {
  unsigned root=0,bit=1u<<30;
  while(bit>n)bit>>=2;
  while(bit) { if(n>=root+bit){n-=root+bit;root=(root>>1)+bit;}else root>>=1;bit>>=2; }
  return root;
}
static void mixPointGains(const int listener[3],const int axis[2],const MixPoint *p,int *left,int *right) {
  if(!p->on)return;
  int mx=p->max,mn=p->min;
  if(mx<1 || mx>32768 || mn<0 || mn>=mx){*left=*right=0;return;}
  int x=p->p[0]-listener[0],y=p->p[1]-listener[1],z=p->p[2]-listener[2];
  if(x>mx||x<-mx||y>mx||y<-mx||z>mx||z<-mx){*left=*right=0;return;}
  unsigned d=mixSqrt((unsigned)(x*x)+(unsigned)(y*y)+(unsigned)(z*z));
  if(d>=(unsigned)mx){*left=*right=0;return;}
  int g=d<=(unsigned)mn?32768:d>=(unsigned)mx?0:(mx-(int)d)*32768/(mx-mn);
  g=(g*g)>>15;
  unsigned dh=mixSqrt((unsigned)(x*x)+(unsigned)(z*z));int pan=0;
  if(dh>8) {
    int cent=dh>=56?32768:((int)dh-8)*32768/48;
    pan=(x*axis[0]+z*axis[1])/(int)dh;
    if(pan>32768)pan=32768;if(pan<-32768)pan=-32768;
    pan=((pan*26214)>>15);pan=(pan*cent)>>15;
  }
  *left=(*left*g)>>15;*right=(*right*g)>>15;
  if(pan>0)*left=(*left*(32768-pan))>>15;
  if(pan<0)*right=(*right*(32768+pan))>>15;
}
static void mixSpatialGains(const MixJob *j,const MixPoint *p,int *left,int *right) {
  mixPointGains(j->listener,j->right,p,left,right);
}

// Правка 313: ME читает банк звуков своим кэшем (схемы ME_MEM_KBOX… viewer/me/mebox.h) — строку кэша ME под блоком VAG сделать
// недействительной перед чтением (модуль задаёт MIX_DATA_FENCE; на главном и на Маке — пусто, счёт не меняется)
#ifndef MIX_DATA_FENCE
#define MIX_DATA_FENCE(p) ((void)0)
#endif

// ---------------------------------------------------------------- PS-ADPCM block (bit-exact with ffmpeg adpcm_psx)
static void mixVag(const unsigned char *b, int *ps1, int *ps2, short *out) {
  static const signed char F0[5] = {0, 60, 115, 98, 122}, F1[5] = {0, 0, -52, -55, -60};
  int sh = b[0] & 15, f = b[0] >> 4, fl = b[1] & 7;
  if (f > 4) f = 0;
  int f0 = F0[f], f1 = F1[f], s1 = *ps1, s2 = *ps2;
  for (int i = 0; i < 14; i++) {
    int by = b[2 + i];
    for (int k = 0; k < 2; k++) {
      int nib = k ? by >> 4 : by & 15, smp = 0;
      if (fl < 7) smp = (((nib ^ 8) - 8) * 4096 >> sh) + (s1 * f0 + s2 * f1) / 64;
      *out++ = (short)(smp > 32767 ? 32767 : smp < -32768 ? -32768 : smp);
      s2 = s1; s1 = smp;
    }
  }
  *ps1 = s1; *ps2 = s2;
}

static void mixSeam(MixJob *j, const MixVoice *v, int n, int i) {   // первый сэмпл после прыжка петли — в окне на индексе n
  j->seams++;
  if (j->nrec < MIX_NSEAM) { MixSeamRec *r = &j->rec[j->nrec++]; r->i = i; r->n = n; r->pos = v->pos; r->step = v->step; }
}

// проход кончился: петля, следующий кусок или конец. 0 — сейчас больше нечего (конец или кольцо потока пусто)
static int mixNextPass(MixJob *j, MixVoice *v, int n, int i) {
  if (v->stream < 0) {
    if (v->loop && v->loopEnd > v->loopStart) {
      v->si = v->loopStart; v->end = v->loopEnd;
      for (int c = 0; c < 2; c++) { v->s1[c] = v->lhist[c * 2]; v->s2[c] = v->lhist[c * 2 + 1]; }
      mixSeam(j, v, n, i);
      return 1;
    }
    v->finished = 1; return 0;
  }
  MixWin *w = &j->w[v->stream];
  if (w->segUsed >= w->nseg) { v->underrun = 1; return 0; }
  const MixSeg *s = &w->seg[w->segUsed++];
  if (s->track < 0) { v->finished = 1; return 0; }
  if (s->track != w->cur) { w->cur = s->track; v->rate = s->rate; }
  v->si = s->start; v->end = s->end;
  for (int c = 0; c < 2; c++) { v->s1[c] = s->hist[c * 2]; v->s2[c] = s->hist[c * 2 + 1]; }
  if (v->segs++ > 0) mixSeam(j, v, n, i);
  return 1;
}

// дозаполнить окно (последний сэмпл остаётся для интерполяции). 0 — новых сэмплов нет
static int mixRefill(MixJob *j, MixVoice *v, int i) {
  if (v->bufLen > 0) {
    v->buf[0][0] = v->buf[0][v->bufLen - 1]; v->buf[1][0] = v->buf[1][v->bufLen - 1];
    v->pos -= (unsigned)(v->bufLen - 1) << 16;
  }
  int n = 1;
  short tmp[2][28];
  while (n + 28 <= MIX_WIN + 1) {
    if (v->si >= v->end) { if (!mixNextPass(j, v, n, i)) break; continue; }
    unsigned b = v->si / 28, off = v->si - b * 28, last = v->end - b * 28;
    if (last > 28) last = 28;
    const unsigned char *p;
    if (v->stream >= 0) {
      MixWin *w = &j->w[v->stream];
      if (w->len - w->used < 32) { v->underrun = 1; break; }
      p = w->win + w->used;
      mixVag(p, &v->s1[0], &v->s2[0], tmp[0]); mixVag(p + 16, &v->s1[1], &v->s2[1], tmp[1]);
      w->used += 32;
    } else {
      p = j->data + v->dataOff + b * 16u * (unsigned)v->ch;
      MIX_DATA_FENCE(p); if (v->ch == 2) MIX_DATA_FENCE(p + 16);
      mixVag(p, &v->s1[0], &v->s2[0], tmp[0]);
      if (v->ch == 2) mixVag(p + 16, &v->s1[1], &v->s2[1], tmp[1]);
    }
    int cnt = (int)(last - off);
    for (int q = 0; q < cnt; q++) v->buf[0][n + q] = tmp[0][off + q];
    if (v->ch == 2) for (int q = 0; q < cnt; q++) v->buf[1][n + q] = tmp[1][off + q];
    n += cnt; v->si = b * 28 + last;
  }
  if (n == 1 && v->finished && !v->tail) { v->buf[0][1] = v->buf[1][1] = 0; n = 2; v->tail = 1; }  // lets the last sample play
  v->bufLen = n;
  return n > 1;
}

// Gains are Q15 (32768 = 1.0), step is 16.16. Volume/pitch changes ramp linearly across the 11.6 ms buffer
// in 32-frame steps (0.7 ms): no per-sample ramp work in the inner loops, no zipper noise.
static void mixVoiceRun(MixJob *j, MixVoice *v) {
  int tgl=v->tgl,tgr=v->tgr;mixSpatialGains(j,&v->point,&tgl,&tgr);
  if(v->spatialStart){v->gl=tgl;v->gr=tgr;v->spatialStart=0;} // keep positional attacks, no first-buffer full-volume transient
  const int n = MIX_FRAMES; const unsigned tstep = v->tstep;
  const int gl0 = v->gl, gr0 = v->gr, st0 = (int)v->step, dl = tgl - gl0, dr = tgr - gr0, ds = (int)tstep - st0;
  int i = 0;
  v->underrun = 0;
  while (i < n) {
    if ((v->pos >> 16) + 1 >= (unsigned)v->bufLen) { if (!mixRefill(j, v, i)) break; continue; }
    const int gl = gl0 + ((dl * i) >> 9), gr = gr0 + ((dr * i) >> 9);
    const unsigned step = (unsigned)(st0 + ((ds * i) >> 9));
    v->step = step;
    unsigned limit = (unsigned)(v->bufLen - 1) << 16;
    int k = (int)((limit - v->pos - 1) / (step ? step : 1)) + 1;
    int sub = 32 - (i & 31);
    if (k > sub) k = sub;
    if (k > n - i) k = n - i;
    unsigned pos = v->pos; int *a = j->acc + 2 * i, *e = a + 2 * k;
    if (v->ch == 1) {
      const short *b = v->buf[0];
      if (gl == gr) {                              // centred: one multiply for both channels
        for (; a < e; a += 2, pos += step) {
          const short *p = b + (pos >> 16); int s0 = p[0];
          int m = ((s0 + (((p[1] - s0) * (int)((pos >> 2) & 0x3FFF)) >> 14)) * gl) >> 15;
          a[0] += m; a[1] += m;
        }
      } else {
        for (; a < e; a += 2, pos += step) {
          const short *p = b + (pos >> 16); int s0 = p[0];
          int s = s0 + (((p[1] - s0) * (int)((pos >> 2) & 0x3FFF)) >> 14);
          a[0] += (s * gl) >> 15; a[1] += (s * gr) >> 15;
        }
      }
    } else {
      const short *bl = v->buf[0], *br = v->buf[1];
      for (; a < e; a += 2, pos += step) {
        unsigned x = pos >> 16; int fr = (pos >> 2) & 0x3FFF, l0 = bl[x], r0 = br[x];
        a[0] += ((l0 + (((bl[x + 1] - l0) * fr) >> 14)) * gl) >> 15;
        a[1] += ((r0 + (((br[x + 1] - r0) * fr) >> 14)) * gr) >> 15;
      }
    }
    v->pos = pos; i += k;
  }
  v->gl = tgl; v->gr = tgr; v->step = tstep;
}

// Задание целиком: сумма звучащих голосов в acc (порядок голосов — как раньше в mixBuffer)
static void mixDspRun(MixJob *j) {
  for (int i = 0; i < MIX_FRAMES * 2; i++) j->acc[i] = 0;
  j->seams = 0; j->nrec = 0;
  for (int k = 0; k < MIX_NV; k++) if (j->v[k].on) mixVoiceRun(j, &j->v[k]);
}

// Правка 313, схема ME_MEM_KERN (viewer/me/mebox.h): задание звука живёт в памяти ядра модуля, главный готовит и забирает его в
// памяти игры; перенос — только того, что нужно счёту и главному: заголовок, звучащие голоса целиком (состояние декодера и окно),
// окна звучащих потоков (вход: заголовок, очередь кусков, байты кольца; выход: заголовок), сумма acc и стыки (выход). Без memcpy:
// этот код идёт в модуле ядра (проверка tests/me/run.py — без вызовов наружу). Сверка бит в бит — tests/me/run.py «Мак, микшер»
static void mixCopyW(void *d, const void *s, unsigned bytes) {
  unsigned *dw = (unsigned *)d; const unsigned *sw = (const unsigned *)s;
  for (unsigned k = 0; k < bytes / 4; k++) dw[k] = sw[k];
}
#define MIX_WIN_HEAD ((unsigned)(unsigned long)&((MixWin *)0)->seg)   // len, used, nseg, segUsed, cur, pad
static void __attribute__((unused)) mixJobIn(MixJob *k, const MixJob *j) {   // главный -> задание в ядре (перед счётом)
  k->data = j->data; k->seams = j->seams; k->nrec = j->nrec;
  for(int i=0;i<3;i++)k->listener[i]=j->listener[i];for(int i=0;i<2;i++)k->right[i]=j->right[i];
  for (int v = 0; v < MIX_NV; v++) { k->v[v].on = j->v[v].on; if (j->v[v].on) mixCopyW(&k->v[v], &j->v[v], sizeof(MixVoice)); }
  for (int s = 0; s < MIX_NSTREAM; s++) {
    const MixWin *a = &j->w[s]; MixWin *b = &k->w[s];
    mixCopyW(b, a, MIX_WIN_HEAD);
    if (!j->v[MIX_NVOICE + s].on) continue;
    mixCopyW(b->seg, a->seg, sizeof(MixSeg) * (a->nseg < MIX_NSEG ? a->nseg : MIX_NSEG));
    mixCopyW(b->win, a->win, (a->len + 3u) & ~3u);
  }
}
static void __attribute__((unused)) mixJobOut(MixJob *j, const MixJob *k) {  // задание в ядре -> главный (после счёта)
  j->seams = k->seams; j->nrec = k->nrec;
  mixCopyW(j->rec, k->rec, sizeof(MixSeamRec) * (k->nrec < MIX_NSEAM ? (unsigned)k->nrec : MIX_NSEAM));
  mixCopyW(j->acc, k->acc, sizeof j->acc);
  for (int v = 0; v < MIX_NV; v++) if (j->v[v].on) mixCopyW(&j->v[v], &k->v[v], sizeof(MixVoice));
  for (int s = 0; s < MIX_NSTREAM; s++) mixCopyW(&j->w[s], &k->w[s], MIX_WIN_HEAD);
}

#endif
