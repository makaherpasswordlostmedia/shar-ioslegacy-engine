// Звук миссий для игры без экрана: таблицы music.sap / sfx.sab (см. msn_audio_host.c)
#ifndef MSN_AUDIO_HOST_H
#define MSN_AUDIO_HOST_H
#include "msn_audio.h"
int msnAudioHostLoad(const char *dir);                 // dir с '/' на конце (build/audio/); 0 = ок
const MsnAudioBackend *msnAudioHostBackend(void);      // NULL — таблиц нет
#endif
