// №976: ход столба звёзд цели (wrench_collect, collectfx.c) и число сторон кольца цели — чистая математика (без PSP); тот же код считает viewer/collectfx.c, lightsprite.h и гейт tests/glint976/host.c.
// Канон кинематики: скорость плавно к нулю, появление и исчезание по smoothstep, без щелчков (звезда не возникает сразу полной яркости, когда фронт проходит ступень).
#ifndef GLINTMOTION976_H
#define GLINTMOTION976_H
#ifndef SPHERE976_N
#define SPHERE976_N 48   // сторон кольца у сферы цели (было 18: прогиб 1,5 % радиуса — 7 см у кольца 5 м; 48 — 0,2 %)
#endif
#ifndef COL976_A
#define COL976_A .4f     // общая прозрачность звёзд столба (доля прежней); .5 давало массу 0,64 от прежней (звезда держит полную яркость дольше прежней линейной рампы)
#endif
#define COL976_T .6f     // время подъёма фронта до верха, с
#define COL976_SOFT 2.6f // на столько метров позади фронта звезда набирает полную яркость
static float gm976Sm(float x) { x = x < 0.f ? 0.f : x > 1.f ? 1.f : x; return x * x * (3.f - 2.f * x); }
// t — время столба, H — высота, life — жизнь; h — высота фронта, a — общая яркость, rad — радиус спирали, м
static void gm976Col(float t, float H, float life, float *h, float *a, float *rad) {
  float tau = t / COL976_T; if (tau > 1.f) tau = 1.f;
  *h = H * (1.f - (1.f - tau) * (1.f - tau));   // скорость фронта 2H/T у основания и 0 у вершины
  float f = gm976Sm((t - .55f) / (life - .55f));
  *a = gm976Sm(t / .2f) * (1.f - f); *rad = .35f * gm976Sm(t / .25f) * (1.f - .4f * f);
}
static float gm976Star(float a, float h, float y) { return a * gm976Sm((h - y) / COL976_SOFT + .15f); }   // яркость звезды на высоте y
#endif
