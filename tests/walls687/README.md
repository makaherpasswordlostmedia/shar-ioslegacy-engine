# №687: стены трасс (L2 C1-5), 17.10
- `protrusion_audit.py LEVEL.shr OUT.tsv` (из корня репозитория, `python3 -I`): выступает ли коллизия (отрезки COL1 и боковые грани ящиков ≥ 6 м) за видимую стену; p > 0 — коллизия торчит в проезд (м)
- `lane_swarm.c`: рой вдоль стен трассы с боковыми смещениями и углами 2…30°, руль 0; `cc -std=c11 -O2 -Iviewer tests/walls687/lane_swarm.c viewer/car.c viewer/col.c -lm`; `./a.out level.shr xl xr z0 z1 dir`
- `wall_swarm_seg.c`: копия tools/cartest/wall_swarm.c Физики + отрезки COL1 как стены (WSW_REG, WSW_NOSEG); `near.c`: коллайдеры в области
