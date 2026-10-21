// Камеры комнат (пункт 11.2, Роб 28.09: «камеры в комнатах — как в оригинале»): данные с диска — локаторы комнаты
// вида 12 (StaticCam) и вида 4 (Spline 0x3000007 + RailCam 0x300000A) со своими TriggerVolume, экспорт —
// tools/interior_export.py (записи 512 Б в блобе комнаты SHG1). Камера снимает, пока Гомер стоит в её триггере.
// Чистый C99 без PSP (проверка на Маке: tests/rooms/cams.sh).
//   StaticCam: позиция — локатор; цель — TargetPosition (точка мира) или, при FollowPlayer, Гомер + TargetPosition
//     (смещение, м); TargetLag — запаздывание цели. RailCam (у всех 129 на диске Behaviour 1): камера на рельсе (ломаная
//     по точкам сплайна) держит горизонтальное расстояние до Гомера в кольце [MinRadius, MaxRadius] — стоит, пока он в
//     кольце, иначе подъезжает к ближайшей точке или отъезжает от неё — до MaxRadius (назад, к началу рельса;
//     ReverseSense — к концу); цель — Гомер + TargetOffset в осях рельса (правка 138: x вбок, y вверх, z вдоль рельса; roomcam.c railLook);
//     PositionLag / TargetLag — запаздывание. FOV — градусы из данных, как у Pure3D — по горизонтали кадра 4:3 (в кадр
//     16:9 переводится по вертикали, Hor+). Смысл полей выведен из данных (кода оригинала нет), он — толкование порта.
//   Декодированы, в движке не используются: TrackRail, TrackDist, AxisPlay (рельс); TransitionTargetRate, Flags, CutInOut,
//     Data (статичная). Смена камеры — срез. Запаздывание L — доля пути к цели за кадр 1/60 с (1 — без запаздывания).
#ifndef ROOMCAM_H
#define ROOMCAM_H
#define ROOM_CAMS 16
#define ROOM_CAM_TRIGS 4
#define ROOM_CAM_PTS 9       // точек рельса на месте в записи (@384); длиннее — массив после таблицы камер (@504 смещение)
#define ROOM_CAM_PTS_MAX 4096   // проверка битого файла, не предел данных (на диске до 13)
#define ROOM_CAM_REC 512
#define ROOM_NEST_RATIO 0.25f   // №229: «вложенная» камера (триггер < 1/4 объёма триггера текущей) берёт кадр сразу (школа camera04, Барт 02); остальные — через ROOM_SWITCH_DELAY от входа
#define ROOM_SWITCH_DELAY 1.f   // правка 172: переход на камеру с запаздыванием в комнате — через 1 с в её триггере (близнец)

typedef struct { int kind; float c[3], half[3], ax[3][3]; } RoomTrig;   // kind: 0 сфера (радиус half[0]), 1 коробка, -1 нет
int roomTrigIn(const RoomTrig *t, float x, float y, float z, float r);   // сфера радиуса r касается объёма (kind -1 — никогда)
int roomTrigRead(RoomTrig *t, const unsigned char *b);                   // 64 Б: u32 вид, центр, полуоси, оси 3x3; 0 = ок

typedef struct {
  char name[32]; int type, ntrig, npts, follow;   // type: 0 статичная, 1 рельс
  float pos[3], target[3], fov, targetLag, posLag, minR, maxR, trackDist;
  int trackRail, reverse, behaviour; float offset[3]; int cut, data;
  RoomTrig trig[ROOM_CAM_TRIGS];
  const float (*pts)[3];         // npts точек рельса — прямо в блобе, из которого разобрана камера (он живёт, пока живёт камера)
  float axisPlay[3];
} RoomCam;
typedef struct { int cur; float eye[3], look[3], t; unsigned in; int newWins; int want; float wantT; int switchOld; float inT[ROOM_CAMS]; } RoomCamState;   // switchOld: 1 — правило задержки 172 до школы (файл roomcamswitchold)   // want/wantT — камера, на которую переходим, и сколько ждём (правка 172)   // cur: камера прошлого кадра (-1 — ходьба); t — место на рельсе
// newWins (правка 186, комнаты): камера, в чей триггер Гомер только что вошёл, берёт кадр, даже если он ещё в триггере текущей
// (близнец v17_house_cam: оригинал переключил на int_sh_path2, когда Гомер был в обоих); in — маска «внутри» прошлого кадра

// таблица камер блоба комнаты RMG1 (заголовок @120 смещение, @124 число): сколько прочитано (0 — нет), <0 — битая.
// Точки рельса не копируются: c->pts указывает в blob — блоб держать, пока нужны камеры (комната: rg.mem, зоны: zcamBuf)
int roomCamsParse(RoomCam *c, int max, const unsigned char *blob, unsigned size);
// камера, в триггере которой точка p (ноги Гомера); текущая остаётся, пока он в её триггере; -1 — ни одной (камера ходьбы)
int roomCamPick(const RoomCam *c, int n, int cur, const float p[3]);
// поза без запаздывания: глаз и точка взгляда для Гомера в p
void roomCamIdeal(const RoomCam *c, const float p[3], float eye[3], float look[3]);
float roomCamFovY(const RoomCam *c);   // вертикальный угол кадра, градусы
// рельс: длина, точка по длине дуги, ближайшая к p, место камеры по поведению Distance (t < 0 — камера только включилась)
float roomRailLen(const RoomCam *c);
void roomRailAt(const RoomCam *c, float t, float o[3]);
float roomRailClosest(const RoomCam *c, const float p[3]);
float roomRailParam(const RoomCam *c, float t, const float p[3]);
void roomRailPose(const RoomCam *c, float t, const float p[3], float eye[3], float look[3]);   // глаз в t и точка взгляда на p
// кадр: выбор камеры и поза с запаздыванием (смена камеры — срез). Возврат: номер камеры или -1 (камера ходьбы)
int roomCamStep(const RoomCam *c, int n, RoomCamState *s, const float p[3], float dt, float eye[3], float look[3], float *fovY);
#endif
