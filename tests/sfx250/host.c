// Гейт правки Роба 250 («эффекты слишком громкие — свести, как в оригинале», видео IMG_7707 2:06–2:13).
// Настоящий микшер порта на Маке: viewer/sound.c + viewer/audio.c (AUDIO_HOST) и пакет звука уровня 1 (build/audio/).
// Мера — та же, что у оригинала: множитель клипа диска на выходе микшера к множителю музыки. Каждый звук рендерится «как в
// игре» (вызов sound.c, слушатель — камера за машиной) и второй раз с единичными шинами, громкостью и мастером (тот же вариант
// клипа и высота: audioTestSeed); МНК двух рендеров даёт множитель. Удар у оригинала мерился так же — МНК клипа диска по выходу
// SPU2 близнеца (build/twins/o4/v13_wreck/audio.wav), музыка sunday_drive — так же.
// Эталоны оригинала (настройки звука по умолчанию; «к музыке» = множитель клипа / множитель музыки sunday_drive 0,183 у близнеца):
//   таран машиной 10,5 м/с (v13_wreck, ram.tsv кадры 3236 и 3416) — small_car_crash, 0,457 (0,431 и 0,483), атака 0,12 с;
//   26 ударов small в записи PS2 build/ps2ref/external/yt-bziOipI4gDI.mp4 (скан клипов диска, перевод в единицы близнеца по
//     sunday_drive двух отрезков записи) — медиана 0,63, слабые 0,40–0,51;
//   мотор famil с газом 0–10 м/с — остаток v13 без музыки −26,1 dBFS / RMS клипа 0,561 = 0,088, к музыке 0,483;
//   щелчок gearshift — в записи PS2 нет (скан 43 мин: не выше 0,36; монета тем же сканом — до 0,90).
//   host PACKDIR/            печатает замеры и OK/FAIL, код 0 — все проверки прошли
//   host PACKDIR/ demo|demofx|demomus OUT.wav   14 с езды на слух: всё / только удары / только музыка
// Сборка и красный контроль — tests/sfx250/run.sh (прежнее сведение: -DSND_250_OLD=1).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "sound.h"
#include "audio.h"

#define FR 512
#define RATE 44100
static const char *pack;
static int fails;
static void check(const char *name, int ok) { printf("%s %s\n", ok ? "OK" : "FAIL", name); fails += !ok; }
static double db(double v) { return 20.0 * log10(v > 1e-9 ? v : 1e-9); }

// ---- журнал эффектов sound.c (правка 135.7): какие клипы запущены
static char logName[64][32]; static int nLog;
static void logFn(const char *l) { if (nLog < 64 && sscanf(l, "SFX %31s", logName[nLog]) == 1) nLog++; }
static int logged(const char *nm) { int n = 0; for (int i = 0; i < nLog; i++) n += !strcmp(logName[i], nm); return n; }

// ---- трим ресурса из пакета (SAB1: заголовок, таблица ресурсов по 48 Б) — множитель «к сырому клипу», как у оригинала
static float trimOf(const char *res) {
  char p[600]; snprintf(p, sizeof p, "%ssfx.sab", pack);
  FILE *f = fopen(p, "rb"); if (!f) return 1.f;
  unsigned h[6]; float t = 1.f;
  if (fread(h, 4, 6, f) == 6) {
    for (unsigned i = 0; i < h[2]; i++) {
      unsigned char r[48]; fseek(f, (long)(h[5] + i * 48), SEEK_SET);
      if (fread(r, 1, 48, f) != 48) break;
      if (!strncmp((const char *)r, res, 24)) { memcpy(&t, r + 28, 4); break; }
    }
  }
  fclose(f); return t;
}

// ---- рендер: n секунд выхода микшера (44,1 кГц стерео, float)
typedef void (*Tick)(int k);
static float *render(float sec, Tick tick, int *frames) {
  int n = (int)(sec * RATE / FR) * FR; float *o = malloc(sizeof(float) * 2 * n); static short b[FR * 2];
  for (int k = 0; k < n; k += FR) { if (tick) tick(k); audioHostMix(b, FR); for (int i = 0; i < FR * 2; i++) o[k * 2 + i] = b[i] / 32768.f; }
  *frames = n; return o;
}
// МНК: множитель a к u по каждому каналу на [from, n)
static void ls(const float *a, const float *u, int from, int n, double g[2]) {
  for (int c = 0; c < 2; c++) {
    double au = 0, uu = 0;
    for (int i = from; i < n; i++) { au += (double)a[i * 2 + c] * u[i * 2 + c]; uu += (double)u[i * 2 + c] * u[i * 2 + c]; }
    g[c] = uu > 0 ? au / uu : 0;
  }
}
static void listener(void);
static void begin(void) {
  if (sndInit(pack) < 0) { printf("FAIL sndInit %s\n", sndError()); exit(2); }
  sndMode(SND_MODE_NORMAL); sndUserVolumes(1, 1, 1, 1); sndLogHook(logFn); nLog = 0;
  for (int i = 0; i < 4; i++) sndFrame(.25f, 4000.f, 3.31f, 3990.7f, 1.f, 0.f, 4000.f, 0.f, 4000.f);   // паузы ударов прошлого замера истекли
  listener();
}
static void unity(void) { for (int b = 0; b < AUDIO_NBUS; b++) { audioBus(b, 1); audioUserVolume(b, 1); } audioMaster(1); }

// ---- геометрия как в игре (viewer/main.c chaseCamUpdate, famil_v: camMag 7,2, camElev 1,23 — 6,8 м назад, 2,4 + 0,9 м вверх,
// подтяжка на скорости ~0,25 м; точка удара — нос машины, 2,3 м вперёд, 0,8 м над землёй). Далеко от уровня: ни зон, ни эмиттеров
#define WX 4000.f
#define WZ 4000.f
static const float CAM[3] = {WX, 3.31f, WZ - 9.3f}, HIT[3] = {WX, 0.8f, WZ};
static void listener(void) { audioListener(CAM[0], CAM[1], CAM[2], 1.f, 0.f); }

// множитель музыки sunday_drive (Normal, громкость игрока 1): эталон «к музыке»
static double musicGain(double g2[2]) {
  int n; float *a, *u;
  begin(); audioMusic(audioTrack("sunday_drive"), 0); a = render(3.f, 0, &n); sndShutdown();
  begin(); unity(); audioMusic(audioTrack("sunday_drive"), 0); u = render(3.f, 0, &n); sndShutdown();
  ls(a, u, RATE / 2, n, g2); free(a); free(u);
  return (g2[0] + g2[1]) / 2;
}
// множитель эффекта: fire() — вызов игры. Какой клип прозвучал — по выходу, не по журналу: каждый ресурс-кандидат рендерится
// единично тем же семенем (тот же номер варианта и высота: у small/medium/large по 3 варианта и одна вилка высоты), берётся тот,
// чей рендер объясняет выход (наибольшая корреляция); его МНК-множитель × трим = множитель к сырому клипу диска, как у оригинала
typedef void (*Fire)(void);
static double fxGain(Fire fire, const char *const *cand, char *clip, int *voices) {
  int n, m; float *a, *u; unsigned seed = 0x5EED250u;
  begin(); listener(); audioTestSeed(seed); fire(); *voices = nLog;
  sndUserVolumes(1, 1, 1, 0);   // реплика Гомера (поток диалогов) — не в этот рендер
  a = render(2.f, 0, &n); sndShutdown();
  double best = -1, gbest = 0; clip[0] = 0;
  for (int k = 0; cand[k]; k++) {
    begin(); unity(); listener(); audioTestSeed(seed); audioPlay(audioFind(cand[k]), 1.f, 0.f, 1.f); u = render(2.f, 0, &m); sndShutdown();
    double g[2], au = 0, aa = 0, uu = 0; ls(a, u, 0, n, g);
    for (int i = 0; i < n * 2; i++) { au += (double)a[i] * u[i]; aa += (double)a[i] * a[i]; uu += (double)u[i] * u[i]; }
    double rho = aa > 0 && uu > 0 ? au / sqrt(aa * uu) : 0;
    if (rho > best) { best = rho; gbest = (g[0] + g[1]) / 2 * trimOf(cand[k]); snprintf(clip, 32, "%s", cand[k]); }
    free(u);
  }
  free(a);
  if (best < 0.9) { printf("  (клип не опознан: лучшая корреляция %.2f у %s)\n", best, clip); clip[0] = 0; }
  return gbest;
}
static const char *const CRASH[] = {"small_car_crash", "medium_car_crash", "large_car_crash", 0};
static void fireRam(void) { sndCarHitCar(10.5f, HIT[0], HIT[1], HIT[2]); }          // таран машины 10,5 м/с (близнец v13)
static void fireWall(void) { sndCarHitWorld(10.5f, 0.f, HIT[0], HIT[1], HIT[2], 0, 0, 0, 0); }   // стена 10,5 м/с
static void fireBump(void) { sndCarHitWorld(4.f, 0.f, HIT[0], HIT[1], HIT[2], 0, 0, 0, 0); }      // лёгкий удар 4 м/с
static void fireFast(void) { sndCarHitWorld(20.f, 0.f, HIT[0], HIT[1], HIT[2], 0, 0, 0, 0); }     // сильный 20 м/с
// предмет уровня со своим звуком (таблица OBJS пакета, kind 0 DynaPhys): тот, что ближе к началу таблицы
typedef struct { float x, y, z, r; unsigned char kind, pad; short res; } XObj;
static float propXYZ[3]; static int propOk;
static void findProp(const char *res) {
  unsigned size; const unsigned char *e = audioBankExt(&size); propOk = 0;
  if (!e || size < 8 || memcmp(e, "SXT1", 4)) return;
  unsigned ns = *(const unsigned *)(e + 4);
  for (unsigned i = 0; i < ns; i++) {
    const unsigned char *s = e + 8 + i * 16;
    if (memcmp(s, "OBJS", 4) || *(const unsigned *)(s + 12) != 20) continue;
    const XObj *o = (const XObj *)(e + *(const unsigned *)(s + 4)); unsigned no = *(const unsigned *)(s + 8);
    for (unsigned k = 0; k < no; k++)
      if (o[k].kind == 0 && o[k].res >= 0 && !strcmp(audioSoundName(o[k].res), res)) { propXYZ[0] = o[k].x; propXYZ[1] = o[k].y; propXYZ[2] = o[k].z; propOk = 1; return; }
  }
}
static void fireProp(void) {   // машина 10,5 м/с сбивает предмет (почтовый ящик) прямо перед камерой
  sndBindObjects(SND_SET_PROPS, 1, propXYZ, 12);
  audioListener(propXYZ[0], propXYZ[1] + 2.5f, propXYZ[2] - 9.3f, 1.f, 0.f);
  sndObjectHit(SND_SET_PROPS, 0, propXYZ[0], propXYZ[1], propXYZ[2], 10.5f);
}
// реплика Гомера (поток диалогов) — голоса не трогаем
static double voiceGain(void) {
  int n, t; float *a, *u; double g[2];
  begin(); t = audioTrack("d_carway_hom_01"); sndVoice(t); a = render(2.f, 0, &n); sndShutdown();
  begin(); unity(); sndVoice(t); u = render(2.f, 0, &n); sndShutdown();
  ls(a, u, 0, n, g); free(a); free(u); return (g[0] + g[1]) / 2;
}
// разгон 0 -> 30 м/с за 12 с с газом: сколько щелчков gearshift (у оригинала — ни одного: скан записи PS2)
static int gearN;
static void engTick(int k) { float t = k / (float)RATE, v = t < 12.f ? 30.f * t / 12.f : 30.f; sndEngine(v, 1.f, SND_ENG_ON); }
// щелчок по выходу: клип gearshift единично (трим 1, без шин) и МНК в буфере, где модель мотора переключила передачу (номер
// передачи — состояние модели AudioStats.gear, одно и то же в прежнем и новом сведении; голос щелчка стартует с этого буфера).
// Множитель — громкость щелчка в разгоне (у прежнего сведения 0,7 × шина 0,88 × мастер 0,7 = 0,43)
static int shiftBuf = -1, lastGear;
static void engTickG(int k) {
  engTick(k);
  AudioStats st; audioStats(&st);
  if (shiftBuf < 0 && lastGear >= 1 && st.gear > lastGear) shiftBuf = k / FR;
  lastGear = st.gear;
}
static double gearClick(double *rhoOut) {
  int n, m; shiftBuf = -1; lastGear = 0;
  begin(); sndCarSetup(33.f); float *a = render(14.f, engTickG, &n); gearN = logged("gearshift"); sndShutdown();
  begin(); unity(); audioTestSeed(1); audioPlay(audioFind("gearshift"), 1.f, 0.f, 1.f); float *u = render(0.5f, 0, &m); sndShutdown();
  double uu = 0, au = 0, aa = 0; for (int i = 0; i < m * 2; i++) uu += (double)u[i] * u[i];
  if (shiftBuf < 0 || (shiftBuf * FR + m) > n) { free(a); free(u); *rhoOut = 0; return -1; }
  const float *p = a + (size_t)shiftBuf * FR * 2;
  for (int i = 0; i < m * 2; i++) { au += (double)p[i] * u[i]; aa += (double)p[i] * p[i]; }
  *rhoOut = aa > 0 && uu > 0 ? au / sqrt(aa * uu) : 0;
  free(a); free(u); return uu > 0 ? au / uu : 0;
}
// мотор с газом 0 -> 10 м/с (как тараны близнеца v13: разгон до 10 м/с): множитель клипа famil = RMS выхода / RMS клипа
static void ramTick(int k) { float t = k / (float)RATE; sndEngine(t < 1.f ? 10.f * t : 10.f, 1.f, SND_ENG_ON); }
static double engineGain(void) {
  int n; double e = 0, c = 0;
  begin(); sndCarSetup(33.f); float *a = render(1.5f, ramTick, &n); sndShutdown();
  for (int i = RATE / 2 * 2; i < n * 2; i++) e += (double)a[i] * a[i];
  int m = n - RATE / 2; free(a);
  begin(); unity(); audioPlay(audioFind("famil"), 1.f, 0.f, 1.f); a = render(1.5f, 0, &n); sndShutdown();   // клип с тримом, без шин
  for (int i = RATE / 2 * 2; i < n * 2; i++) c += (double)a[i] * a[i];
  free(a);
  return sqrt(e / (2.0 * m)) / (sqrt(c / (2.0 * (n - RATE / 2))) / trimOf("famil"));
}

// демо на слух (tests/sfx250/run.sh кладёт build/sfx250/demo_{old,new}.wav): 14 с езды как в игре — музыка свободной езды,
// разгон 0 -> 25 м/с (переключение передачи на ~21 м/с), удары о стену 5 / 10,5 / 15 / 20 м/с на 2, 5, 8 и 11 с
static void demoTick(int k) {
  float t = k / (float)RATE, v = t < 10.f ? 2.5f * t : 25.f; sndEngine(v, 1.f, SND_ENG_ON);
  static const float at[4] = {2.f, 5.f, 8.f, 11.f}, sp[4] = {5.f, 10.5f, 15.f, 20.f};
  for (int i = 0; i < 4; i++) if (t <= at[i] && t + (float)FR / RATE > at[i]) sndCarHitWorld(sp[i], 0.f, HIT[0], HIT[1], HIT[2], 0, 0, 0, 0);
  sndFrame((float)FR / RATE, CAM[0], CAM[1], CAM[2], 1.f, 0.f, HIT[0], 0.f, HIT[2] - 2.3f);
}
static int demo(const char *wav, int part) {   // part 0 — всё, 1 — только удары (музыка и мотор в 0), 2 — только музыка
  int n; begin(); sndCarSetup(33.f); sndUserVolumes(part == 1 ? 0 : 1, part == 2 ? 0 : 1, part ? 0 : 1, 0); sndMusic(SND_MUS_FREEROAM);
  float *a = render(14.f, demoTick, &n); sndShutdown();
  FILE *f = fopen(wav, "wb"); if (!f) return 2;
  unsigned bytes = (unsigned)n * 4, v; unsigned short s;
  fwrite("RIFF", 1, 4, f); v = 36 + bytes; fwrite(&v, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f); v = 16; fwrite(&v, 4, 1, f);
  s = 1; fwrite(&s, 2, 1, f); s = 2; fwrite(&s, 2, 1, f); v = RATE; fwrite(&v, 4, 1, f); v = RATE * 4; fwrite(&v, 4, 1, f);
  s = 4; fwrite(&s, 2, 1, f); s = 16; fwrite(&s, 2, 1, f); fwrite("data", 1, 4, f); fwrite(&bytes, 4, 1, f);
  for (int i = 0; i < n * 2; i++) { float x = a[i] * 32768.f; short q = (short)(x > 32767 ? 32767 : x < -32768 ? -32768 : x); fwrite(&q, 2, 1, f); }
  fclose(f); free(a); printf("demo %s: %.1f с\n", wav, n / (double)RATE); return 0;
}

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: host PACKDIR/ [demo|demofx|demomus OUT.wav]\n"); return 2; }
  pack = argv[1];
  if (argc > 3 && !strcmp(argv[2], "demo")) return demo(argv[3], 0);
  if (argc > 3 && !strcmp(argv[2], "demofx")) return demo(argv[3], 1);
  if (argc > 3 && !strcmp(argv[2], "demomus")) return demo(argv[3], 2);
  double gm2[2], gm = musicGain(gm2);
  printf("музыка sunday_drive: множитель L %.4f R %.4f (шина 0,78 x мастер)\n", gm2[0], gm2[1]);
  char clip[32]; int nv = 0;
  // 1) таран 10,5 м/с — эталон оригинала: small_car_crash, 0,457 к музыке (−6,8 дБ; тараны 12 и 13: 0,431 и 0,483)
  double g = fxGain(fireRam, CRASH, clip, &nv), r = g / gm;
  printf("таран 10,5 м/с: %s, к музыке %.3f (%.1f дБ); оригинал small_car_crash 0,457 (-6,8 дБ)\n", clip, r, db(r));
  check("250.1 таран 10,5 м/с: клип small_car_crash, как у оригинала (близнец v13, тараны 12 и 13)", !strcmp(clip, "small_car_crash"));
  check("250.2 таран 10,5 м/с: удар к музыке -6,8 дБ ±1,5 (оригинал 0,457)", fabs(db(r) - db(0.457)) <= 1.5);
  double rw = fxGain(fireWall, CRASH, clip, &nv) / gm; char wclip[32]; snprintf(wclip, 32, "%s", clip);
  printf("стена 10,5 м/с: %s, к музыке %.3f (%.1f дБ)\n", wclip, rw, db(rw));
  check("250.3 стена 10,5 м/с — тот же удар, что таран (клип и громкость)", !strcmp(wclip, "small_car_crash") && fabs(db(rw) - db(0.457)) <= 1.5);
  double rb = fxGain(fireBump, CRASH, clip, &nv) / gm; printf("лёгкий удар 4 м/с: %s, к музыке %.3f (%.1f дБ)\n", clip, rb, db(rb));
  char fclip[32]; double rf = fxGain(fireFast, CRASH, fclip, &nv) / gm; printf("сильный удар 20 м/с: %s, к музыке %.3f (%.1f дБ)\n", fclip, rf, db(rf));
  check("250.4 удар громче с силой: 4 < 10,5 <= 20 м/с", rb < r && r <= rf);
  // сильные удары оригинала (запись PS2, 26 ударов small): потолок 0,63 к музыке (−4,0 дБ; medium и large там же: 0,47–0,74)
  check("250.5 сильный удар 20 м/с: к музыке -4,0 дБ ±1,5 (потолок оригинала 0,63)", fabs(db(rf) - db(0.63)) <= 1.5);
  // 2) предмет со своим звуком (почтовый ящик) 10,5 м/с — та же группа ударов (collide.spt): громкость удара машины той же силы
  //    с тримом своего клипа (0,49 против 0,75 у small_car_crash)
  begin(); findProp("car_hit_mailbox"); sndShutdown();
  if (propOk) {
    static const char *const MAIL[] = {"car_hit_mailbox", 0};
    double rp = fxGain(fireProp, MAIL, clip, &nv) / gm, want = r * 0.49 / 0.75;
    printf("почтовый ящик 10,5 м/с: %s, к музыке %.3f (%.1f дБ); удар машины той же силы с тримом 0,49: %.3f\n", clip, rp, db(rp), want);
    check("250.6 предмет 10,5 м/с: клип предмета, громкость удара машины той же силы (±0,5 дБ)", !strcmp(clip, "car_hit_mailbox") && fabs(db(rp) - db(want)) <= 0.5);
  } else check("250.6 предмет car_hit_mailbox в таблице OBJS пакета", 0);
  // 3) мотор и щелчок на повышении передачи
  double ge = engineGain(); printf("мотор, газ 0 -> 10 м/с: к музыке %.3f (%.1f дБ); оригинал 0,483 (-6,3 дБ)\n", ge / gm, db(ge / gm));
  check("250.7 мотор с газом к музыке -6,3 дБ ±1 (оригинал: остаток близнеца v13 −26,1 dBFS / клип famil, музыка 0,183)", fabs(db(ge / gm) - db(0.483)) <= 1.0);
  double grho, gk = gearClick(&grho);
  printf("разгон 0 -> 30 м/с: переключение в буфере %d (%.2f с); щелчок gearshift по выходу — множитель %.3f (к музыке %.1f дБ, "
         "корреляция %.2f); в журнале %d\n", shiftBuf, shiftBuf * (double)FR / RATE, gk, db(fabs(gk) / gm), grho, gearN);
  check("250.8 разгон: передача переключилась, щелчка gearshift нет — по выходу тише музыки на 20 дБ и больше (у оригинала нет: "
        "скан записи PS2)", shiftBuf > 0 && fabs(gk) / gm < 0.1);
  // 4) голоса и музыка не тронуты
  double gv = voiceGain(); printf("реплика Гомера: множитель %.4f, к музыке %.3f (%.1f дБ)\n", gv, gv / gm, db(gv / gm));
  check("250.9 голос к музыке — как в тюнере диска 1,00/0,78 (+2,2 дБ), без изменений", fabs(db(gv / gm) - db(1.0 / 0.78)) <= 0.1);
  check("250.10 музыка: множитель шины 0,78 x мастер 0,7 (без изменений)", fabs(gm - 0.78 * 0.7) <= 0.01);
  printf("RESULT %s (%d провалов)\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
