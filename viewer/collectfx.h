// Эффект цели миссии SetCollectibleEffect (04.10, «подтяни все объекты миссий»; запись PS2 10:34.7: въезд в сферу цели
// у дома Фландерса — столб голубого света и голубые искры). Данные — viewer/collectfx_data.h (tools/collectfx_export.py по
// диску): составной объект эффекта (wrench_collect, bonestorm_explosion, carfish, lsrexpld) = квады свечения с дорожкой
// ширины/высоты/цвета по кадрам (рисуются fxSprite, текстуры fx.shr) + системы частиц fx.shr (fxBurst, один раз).
// Кто зовёт: viewer/msn_view.c — предмет собран (точки гонок, ящики доставки и тарана: MsnPropsApi.item_collected) и цель
// goto пройдена (carsphere / triggersphere) — там, где игрок (машина / Гомер) вошёл в объём цели (на записи столб света
// встаёт у машины: объём цели у дома Фландерса 44 x 72 м, центр локатора далеко). Звука у эффекта нет (на записи PS2 при въезде в сферу —
// только «этап пройден», ui_sfx.c; звук ключа wrench_collect — у гаечных ключей мира, viewer/main.c onWrench).
#ifndef COLLECTFX_H
#define COLLECTFX_H

typedef struct { const char *tex; int blend; float off[3]; float fps; int nfr; const float (*tr)[6]; } CfxBill;   // blend как fxSprite
typedef struct { const char *sys; float off[3]; } CfxPs;
typedef struct { const char *name; float dur; int nbill; const CfxBill *bill; int nps; const CfxPs *ps; } CfxDef;

extern int cfxOld;          // 1 — как до 04.10: эффекта нет (красный контроль, флаг сценария cfxold)
extern unsigned cfxSprites; // квадов эффекта отдано fxSprite с начала (служебный счётчик для гейта)
// эффект name в точке pos (мир); -> частей запущено (систем частиц + квадов), 0 — нет эффекта / "none" / cfxOld
int  cfxPlay(const char *name, const float pos[3]);
// раз в кадр ДО fxDraw: квады живых эффектов -> fxSprite на этот кадр, время вперёд на dt
void cfxFrame(float dt);
void cfxReset(void);        // убрать все (смена уровня, выход из миссий)
int  cfxActive(void);       // живых эффектов (квады ещё горят)

#endif
