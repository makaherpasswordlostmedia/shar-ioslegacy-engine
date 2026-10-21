// Звуки интерфейса в игре: события HUD и паузы (viewer/ui.c uiPopHook) -> ресурсы звуковых таблиц диска
// (sound/scripts/world.spt, frontend.spt), играет viewer/sound.c. Плюс служебные флаги гейта анимаций HUD.
#ifndef SHAR_UI_SFX_H
#define SHAR_UI_SFX_H
// один раз после uiInit и sndInit; log — строки гейта (smoke.txt), может быть NULL
void uiSfxInit(void (*log)(const char *));
// флаг сценария смоука (uipulse, uipulse0, uihnr, uihnrold, uipop, uipop0, uipopmsg, uisfx0, uioff): 1 — обработан
int  uiSfxService(const char *flag, float a);
#endif
