#ifndef SHAR_BONUS_AUDIO_H
#define SHAR_BONUS_AUDIO_H
#include "bonus.h"
#include "msncar.h"
#ifndef BONUS_SOUND_OLD
#define BONUS_SOUND_OLD 0
#endif
// Музыка заезда по трассам (09.10): событие SuperSprint композиции l1/l2/l7_music.rms — выбор logic_or из пяти мелодий Casio
// (casio_tune01/02/07/08/09; у оригинала — один из пяти). ПРАВИЛО ПОРТА: трасса N — альтернатива (N−1) mod 5 по порядку композиции,
// у каждой трассы своя мелодия (трассы 6 и 7 — снова 01 и 02: мелодий пять, трасс семь). BONUS_TUNE_OLD=1 — Casio01 на всех трассах
#ifndef BONUS_SCREENS_OLD
#define BONUS_SCREENS_OLD 0
#endif
#ifndef BONUS_TUNE_OLD
#define BONUS_TUNE_OLD BONUS_SCREENS_OLD
#endif
typedef struct {int beep,lastBeep,music,win,lose,racing,result,paused;} BrAudio;
void brAudioInit(BrAudio *a);
void brAudioFrame(BrAudio *a,const BonusRace *r,const Car *player,const char *name,const MsnCars *cars,float dt,float throttle,int paused);
const char *brAudioTuneName(int track);   // имя дорожки music.sap мелодии трассы 1..7
void brAudioTune(BrAudio *a,int track);   // после brAudioInit: мелодия заезда трассы
// Правка Роба (бонус-игра до оригинала, 10.10; ps2-obs-bonus-answers В134): оригинал читает с диска на прямом b01 casio_tune09, на обратном
// b01 — casio_tune07 (слухом не подтверждено; остальные трассы — прежнее правило порта выше). BONUS_TUNE_B01_OLD=1 — только правило порта
#ifndef BONUS_TUNE_B01_OLD
#define BONUS_TUNE_B01_OLD 0
#endif
// Правка Роба 453 (10.10: «музыка, скорее всего, одна на все трассы»): одна мелодия на всех трассах — casio_tune09 (её оригинал читает на прямом b01;
// остальные трассы не сняты) — правило порта. BONUS_TUNE_ONE_OLD=1 — мелодия трассы (правило 09.10) и b01 по направлению (BONUS_TUNE_B01_OLD)
#ifndef BONUS_TUNE_ONE_OLD
#define BONUS_TUNE_ONE_OLD 0
#endif
const char *brAudioTuneNameDir(int track,int reverse);
void brAudioTuneDir(BrAudio *a,int track,int reverse);
void brAudioResult(BrAudio *a,int winner);
void brAudioStop(BrAudio *a);
#endif
