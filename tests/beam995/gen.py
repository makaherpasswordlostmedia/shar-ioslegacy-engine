#!/usr/bin/env python3
# №995: сценарий тарелки L7 (рецепт tests/missions/boss_l7.sh): вид сбоку, сверху, из машины в луче; каждый вид сначала beam995 0 (TEST70), потом 1 (новое); счёт BEAM995 и снимки b995_<вид>_off/on
UFO = "-121.5 601.8 0.0"; PLAY = "-116.1 580.0 0.0"
o = ["# №995: тарелка L7, три вида, beam995 0 затем 1", "flag menu", "flag lvset 7", "scene B995_BOOT", "wait 1.5", "press cross", "wait 9", "flag msnufo"]
V = [('side', "cam -160 22 601.8 1 -0.12 0 70", PLAY), ('top', "cam -121.5 62 575 0 -0.75 0.66 70", PLAY), ('low', "cam -121.5 3 650 0 0.28 -1 70", PLAY), ('car', None, UFO)]
for n, cam, g in V:   # миссия перезапускается на каждый вид: таймер этапа короткий (TIMED OUT на 15-й секунде)
    o += [f"scene B995_{n.upper()}", "flag msnmainat 202", "wait 0.8", "press cross 0.2", f"goto {g}", "wait 1.2"]
    if cam: o.append(cam)
    for on, tag in ((0, 'off'), (1, 'on')):
        o += [f"flag beam995 {on}", "wait 0.9", "flag beam995stat", f"shot b995_{n}_{tag}"]
    o += ["cam off", "wait 0.3"]
o += ["flag msnufo", "end"]
open('ufo.txt', 'w').write("\n".join(o) + "\n")
