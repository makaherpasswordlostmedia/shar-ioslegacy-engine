// Родные AAX-мигалки полиции, без состояния мира и аллокаций
#ifndef SHAR_POLICE_FX_H
#define SHAR_POLICE_FX_H
#include "msncar.h"
typedef struct { float u,v; unsigned color; float x,y,z; } PfVertex;
typedef struct { PfVertex v[6]; int flare; } PfQuad;
extern int policeFxOld;
int policeFxQuads(const McCar *car,float time,const float eye[3],PfQuad out[4]);
// правка Роба 495 (Г16): четыре больших луча NOAX с диска (siren6/8/7/9), качаются клипом суставов; policeBeamOld=1 / -DPOLICE_BEAM_OLD=1 — без лучей
extern int policeBeamOld;
extern int policeSirenFadeOld;   // №538: 1 — лучи без затухания по углу к камере
float pfBeamFade(const float w[4][3], const float eye[3]);   // 0 ребром к камере .. 1 анфас, гладко
#define PF_BEAMS 4
int policeFxBeams(const McCar *car,float time,const float eye[3],PfQuad out[PF_BEAMS]);
int policeFxDraw(const McCar *car,float time,const float eye[3]);
#endif
