// Гейт громкости фона (правка Роба 161 «птицы громко» + аудит 09.10 п. 22): уровень в дБ на выходе настоящего микшера порта
// (viewer/sound.c + viewer/audio.c, AUDIO_HOST) с пакетом звука уровня 1 (build/audio/). Мак, CPU, без эмулятора.
// Эталон PS2 — knowledge/facts/ps2-ambience-level.yaml (В25, близнец build/twins/o4/v25_audio/audio.wav, RMS по 0,5 с):
//   пешком стоит, только фон amb_l1_suburbs_day — −37 dBFS (−36 … −37,5);
//   в машине: музыка sunday_drive + мотор на холостых + фон — −25,5 dBFS (−23 … −27).
// Абсолютные dBFS порта и близнеца не сравнимы (мастер другой: музыка sunday_drive у порта ×0,546, у близнеца ×0,183), поэтому
// мера — разность «фон пешком» минус «в машине» в одном и том же выходе: у PS2 −11,5 дБ (крайние −9 … −14,5).
//   host PACKDIR/   печатает замеры и OK/FAIL, код 0 — все проверки прошли
// Красный контроль — tests/amb161/run.sh (прежнее: -DAMB161_OLD=1, набор шин режима затирает ×AMB_GAIN при старте).
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

static int carOn;
static void tick(int k) { (void)k; if (carOn) sndEngine(0.f, 0.f, SND_ENG_ON); }   // мотор на холостых, как в записи PS2 (кадры 0–300)
// RMS выхода (оба канала) на [from, sec) секунд, dBFS
static double rmsDb(float sec, float from) {
  int n = (int)(sec * RATE / FR) * FR, f0 = (int)(from * RATE); static short b[FR * 2]; double e = 0; long cnt = 0;
  for (int k = 0; k < n; k += FR) {
    tick(k); audioHostMix(b, FR);
    if (k >= f0) for (int i = 0; i < FR * 2; i++) { double x = b[i] / 32768.0; e += x * x; cnt++; }
  }
  return db(sqrt(e / (cnt ? cnt : 1)));
}
static void begin(void) {
  if (sndInit(pack) < 0) { printf("FAIL sndInit %s\n", sndError()); exit(2); }
  sndUserVolumes(1, 1, 1, 1);
  audioListener(4000.f, 3.f, 4000.f, 1.f, 0.f);
  sndLevelStart(4000.f, 0.f, 4000.f);   // атмосфера старта уровня 1: amb_l1_suburbs_day (как у дома в записи PS2)
}
#define FOOT_PS2 (-36.6)   // В25: пешком, только фон (медиана окон 0,5 с)
#define CAR_PS2 (-26.0)    // В25: в машине, музыка + мотор на холостых + фон
static void unity(void) {   // единичные шины, громкость игрока и мастер; шина фона — с поправкой на AMB_GAIN (audioBus его умножает)
  for (int b = 0; b < AUDIO_NBUS; b++) { audioBus(b, 1); audioUserVolume(b, 1); }
#if !(defined(AMB161_OLD) && AMB161_OLD)
  audioBus(AUDIO_BUS_AMBIENCE, 1.f / audioTestAmbGain());
#endif
  audioMaster(1);
  audioStreamSet(AUDIO_ST_AMBIENCE, 1.f, 0.f);   // правка 422: сырой клип — без шага атмосферы улицы
}
static const char *ambName(void) { AudioStats s; audioStats(&s); return s.track[AUDIO_ST_AMBIENCE] >= 0 ? audioTrackName(s.track[AUDIO_ST_AMBIENCE]) : "-"; }

// dump: сырой клип (единичные шины и мастер) в WAV 44,1 кГц для МНК против записи PS2 (tools/research/amb161_fit.py)
static int dump(const char *what, float sec, const char *wav) {
  begin(); audioAmbience(-1, 0); unity(); carOn = 0;
  if (!strcmp(what, "amb")) sndLevelStart(4000.f, 0.f, 4000.f); else audioMusic(audioTrack(what), 0);
  int n = (int)(sec * RATE / FR) * FR; FILE *f = fopen(wav, "wb"); if (!f) return 2;
  unsigned bytes = (unsigned)n * 4, v; unsigned short s; static short b[FR * 2];
  fwrite("RIFF", 1, 4, f); v = 36 + bytes; fwrite(&v, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f); v = 16; fwrite(&v, 4, 1, f);
  s = 1; fwrite(&s, 2, 1, f); s = 2; fwrite(&s, 2, 1, f); v = RATE; fwrite(&v, 4, 1, f); v = RATE * 4; fwrite(&v, 4, 1, f);
  s = 4; fwrite(&s, 2, 1, f); s = 16; fwrite(&s, 2, 1, f); fwrite("data", 1, 4, f); fwrite(&bytes, 4, 1, f);
  for (int k = 0; k < n; k += FR) { audioHostMix(b, FR); fwrite(b, 2, FR * 2, f); }
  fclose(f); sndShutdown(); return 0;
}

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: host PACKDIR/ [dump amb|TRACK SEC OUT.wav]\n"); return 2; }
  pack = argv[1];
  if (argc > 5 && !strcmp(argv[2], "dump")) return dump(argv[3], (float)atof(argv[4]), argv[5]);
  // 1) пешком стоит: режим OnFoot, музыка молчит (туба — отдельный отрезок записи, здесь не звучит), только фон
  begin(); sndOnFoot(1); sndMusic(SND_MUS_OFF); sndMode(SND_MODE_ONFOOT); carOn = 0;
  double amb = rmsDb(8.f, 2.f); char an[64]; snprintf(an, sizeof an, "%s", ambName()); sndShutdown();
  // 2) в машине: режим Normal, музыка sunday_drive, мотор famil на холостых, тот же фон
  begin(); sndOnFoot(0); sndMode(SND_MODE_NORMAL); sndCarSetup(33.f); carOn = 1; audioMusic(audioTrack("sunday_drive"), 0);
  double car = rmsDb(8.f, 2.f); sndShutdown();
  // 3) единичные шины, громкость и мастер: сырой клип фона и сырой клип музыки (множитель = RMS выхода / RMS сырого клипа)
  begin(); unity(); carOn = 0; double rawA = rmsDb(8.f, 2.f); sndShutdown();
  begin(); audioAmbience(-1, 0); sndMode(SND_MODE_NORMAL); carOn = 0; audioMusic(audioTrack("sunday_drive"), 0); double mus = rmsDb(8.f, 2.f); sndShutdown();
  begin(); audioAmbience(-1, 0); unity(); carOn = 0; audioMusic(audioTrack("sunday_drive"), 0); double rawM = rmsDb(8.f, 2.f); sndShutdown();
  double gA = amb - rawA, gM = mus - rawM;   // дБ: множитель фона пешком и музыки к сырому клипу
  // PS2: фон пешком −36,6 dBFS (медиана окон 0,5 с, tools/research/amb161_fit.py) при том же сыром клипе — множитель фона;
  // музыка sunday_drive у близнеца ×0,183 (МНК, tests/sfx250). Фон к музыке у PS2 — верхняя граница (в записи пешком есть и
  // другие тихие звуки), поэтому допуск вниз 3 дБ, вверх 1 дБ
  double ps2A = FOOT_PS2 - rawA, ps2rel = ps2A - db(0.183), rel = gA - gM, d = amb - car;
  printf("фон пешком (%s): %.1f dBFS, в машине (музыка + мотор + фон): %.1f dBFS; разность %.1f дБ (PS2 %.1f и %.1f: %.1f дБ)\n",
         an, amb, car, d, FOOT_PS2, CAR_PS2, FOOT_PS2 - CAR_PS2);
  printf("множитель фона пешком %.3f (сырой фон %.1f dBFS), музыки %.3f; фон к музыке %+.1f дБ, PS2 %+.1f дБ (фон %.3f, музыка 0,183)\n",
         pow(10, gA / 20), rawA, pow(10, gM / 20), rel, ps2rel, pow(10, ps2A / 20));
  // правка 422: улица на sndTestAmbOutDb() дБ тише (вкус Роба, не PS2) — ожидания 161.2–161.4 сдвинуты на этот шаг флагом сборки,
  // допуски прежние; AMB422_OLD=1 — шаг 0, ожидания как раньше
  const double out = sndTestAmbOutDb();
  double want = 1.0 * audioTestAmbGain() * 0.7 * pow(10, out / 20);   // тюнер OnFoot 1,0 × AMB_GAIN × мастер 0,7 × шаг улицы 422
  printf("множитель фона этой сборки AMB_GAIN %.2f: ждём %.3f, на выходе %.3f (%+.1f дБ)\n", audioTestAmbGain(), want, pow(10, gA / 20), gA - db(want));
  check("161.1 звучит атмосфера старта уровня 1 amb_suburbs_day (как у дома в записи PS2)", !strcmp(an, "amb_suburbs_day"));
  check("161.2 фон пешком к музыке как у PS2 (+ шаг 422): от −3 до +1 дБ к замеру В25", rel - ps2rel - out >= -3.0 && rel - ps2rel - out <= 1.0);
  check("161.3 фон пешком тише машины в пределах записи PS2 (−9 … −14,5 дБ, карточка В25; + шаг 422)", d - out <= -9.0 && d - out >= -14.5);
  check("161.4 множитель фона AMB_GAIN действует на выходе (±0,3 дБ): набор шин режима его не затирает", fabs(gA - db(want)) <= 0.3);
  // 422: улица тише на 3 дБ к тюнеру диска (вкус Роба) — множитель фона пешком на выходе; комната (правка 345) — как была
  double base = db(want) - out;   // множитель фона без шага 422 (тюнер × AMB_GAIN × мастер)
  begin(); sndOnFoot(1); sndMusic(SND_MUS_OFF); sndMode(SND_MODE_ONFOOT); carOn = 0; sndRoom("KwikEMart");
  double room = rmsDb(8.f, 2.f); char rn[64]; snprintf(rn, sizeof rn, "%s", ambName()); sndShutdown();
  begin(); unity(); carOn = 0; audioAmbience(audioTrack(rn), 0); double rawR = rmsDb(8.f, 2.f); sndShutdown();
  double gR = room - rawR;
  printf("422: улица к комнате %+.1f дБ (шаг сборки %.1f); комната %s %+.1f дБ к тюнеру\n", gA - gR, out, rn, gR - base);
  check("422.1 атмосфера улицы на 3 дБ тише атмосферы комнаты при том же тюнере (вкус Роба, ±0,3 дБ)", fabs(gA - gR + 3.0) <= 0.3);
  check("422.2 атмосфера комнаты (KwikEMart) без изменений (±0,3 дБ к тюнеру)", !strcmp(rn, "amb_room_small_01") && fabs(gR - base) <= 0.3);
  printf("RESULT %s (%d провалов)\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
