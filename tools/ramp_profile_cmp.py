#!/usr/bin/env python3
"""Сверка профиля подъёма порта и оригинала по расстоянию до кромки (колонка along): vy двух видов (скорость центра масс; разность y за шаг 25 Гц, как в twin.c) и тангаж.
   ramp_profile_cmp.py PORT_TRACE.tsv PS2_jump.tsv [first_frame] — PORT_TRACE из tests/jumps/twin.sh --trace DIR (t x y z along v vy grounded pitch roll wheels, 25 Гц),
   PS2 — build/twins/o4/*/jump.tsv (кадр x y z курс v vy cmy фаза along тангаж, шаг 2 кадра PAL = 25 Гц). Оси оригинала зеркальны порту по z, along у обоих растёт к кромке."""
import sys
import numpy as np
port=np.loadtxt(sys.argv[1]); 
rows=[l.split('\t') for l in open(sys.argv[2]).read().splitlines()[1:]]
ff=int(sys.argv[3]) if len(sys.argv)>3 else 0

# колонки PS2: 0 кадр, 1 x, 2 y, 3 z, 4 курс, 5 v, 6 vy, 7 cmy, 8 фаза, 9 along, 10 тангаж
ps=np.array([[float(r[0]),float(r[2]),float(r[6]),float(r[9]),float(r[10])] for r in rows if int(r[0])>=ff and r[9]!=''])
pa=port[:,4]; py=port[:,2]; pvy=port[:,6]; ppitch=port[:,8]
pydiff=np.r_[np.nan,np.diff(py)*25]
sa=ps[:,3]; sy=ps[:,1]; svy=ps[:,2]; spitch=ps[:,4]
sydiff=np.r_[np.nan,np.diff(sy)*25]
def at(a,arr,x):
    i=np.argsort(a); return float(np.interp(x,a[i],np.nan_to_num(arr[i])))
print(f"{'до кромки, м':>12} | {'vy cm ор':>8} {'порт':>6} | {'vy y-разн ор':>12} {'порт':>6} | {'тангаж ор':>9} {'порт':>6}")
for x in [-30,-24,-20,-16,-14,-12,-10,-8,-6,-4,-2,0,2,4]:
    if x<sa.min() or x>sa.max() or x<pa.min() or x>pa.max(): continue
    print(f"{x:12.0f} | {at(sa,svy,x):8.2f} {at(pa,pvy,x):6.2f} | {at(sa,sydiff,x):12.2f} {at(pa,pydiff,x):6.2f} | {at(sa,spitch,x):9.1f} {at(pa,ppitch,x):6.1f}")
m=(sa>-20)&(sa<2); n=(pa>-20)&(pa<2)
print(f"максимум на отрезке -20…+2 м: vy ЦМ ор {svy[m].max():.2f} порт {pvy[n].max():.2f}; y-разность ор {np.nanmax(sydiff[m]):.2f} порт {np.nanmax(pydiff[n]):.2f}; тангаж ор {spitch[m].max():.1f} порт {ppitch[n].max():.1f}")
