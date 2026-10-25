# Status

Where the port stands against the original PS2 game, as of October 25, 2026 (build 66). Every row says how it was checked, because a Mac emulator run does not prove anything about PSP speed or a story ending.

- **Hardware:** PSP-2000 with custom firmware, PAL disc. Nothing else has been tested.
- **Latest hardware tour:** a scripted run of 33 scenes across all 7 levels (build "TEST62", second run). The final build ("TEST64") is on the PSP but has not been measured yet, so the numbers below belong to the previous build.
- **How it was checked:** *hardware* = scripted tour or play on a real PSP; *emulator* = headless PPSSPP on a Mac (logic only, speed means nothing); *code* = read, never run.

## What works, what is partial, what is missing

| Area | Status | Checked on |
|---|---|---|
| Levels 1 to 7 load and run end to end in the tour | works | hardware |
| Player character per level (Bart, Lisa, Marge, Apu, Homer) | works | hardware |
| 16:9 3D, menus, HUD and loading screens rebuilt from the original files | works | hardware |
| Pause, options, radar, mission select | works, one reported glitch not reproduced | hardware |
| Save slots, SAVE, RESUME, level unlocking | works | hardware |
| Sound and music streaming (Media Engine mixer) | works: 0 late buffers in 1014 s | hardware |
| Music on every level | plays on all 7 in the tour log; listened to on level 1 only | hardware (log), ear on L1 |
| Story missions, level 1 | works when played by hand; bots finish 7 of 13 runs, the rest hit their time limit | hardware (by hand), bots |
| Story missions, levels 2 to 7 | partial: starts verified, full playthrough not proven | emulator, bots |
| Level 7 UFO tractor beam (`destroyboss` objective) | works since build 65: the UFO and its beam are in the world, missions 3, 5, 6 and 7 complete; not yet played on hardware | emulator |
| Street races | partial: start verified on L2 to L7, rival pace differs from PS2 | emulator |
| Bonus missions | partial | emulator, bots |
| Wager race | partial: start verified, win not proven | emulator |
| Bonus game (7 tracks) | implemented, not tested on hardware | emulator |
| Cutscenes (16 videos) | on the card; verified on hardware: intro, logos, one clip; the rest not | hardware (partial), code |
| Ending, save after the last mission, credits | implemented; a hang in the ending scene was bypassed, cause not found; not tested to the credits on hardware | emulator |
| Poles and lamp posts when hit | works: fall like the PS2 (whole, pivoting at the base), fall time within 0.3 s of PS2 recordings at four speeds on level 1; other levels and large trees not recorded on the PS2 | emulator vs PS2 recording |
| Player-character cars, damage, smoke, wheels | partial: tuned against PS2 recordings for two vehicles only | hardware (level 1), emulator |
| Police and Hit & Run | partial: verified on hardware in early builds, not in recent tours | emulator |
| Traffic and pedestrians | partial: density and variety not compared with PS2 | hardware, emulator |
| On foot: run, jump, kick, enter and exit cars, interiors | works on level 1; interiors on levels 2 to 7 not re-verified | hardware (L1), emulator |
| Collectibles: cards, wasps, gags | partial: all 7 levels have data, level 1 verified | hardware (L1), emulator |
| Phone booth, shop, wardrobe | works on level 1; levels 2 to 7 partial | hardware (L1), emulator |
| Dialogue voice | level 1 verified; levels 2 to 7 not listened to | ear on L1 |
| Subtitles | missing: the disc data has none | n/a |
| Repeat a finished race | missing (audit, October 16) | code |
| Cinema mission on level 3 | missing (audit, October 16) | code |
| Reset Car | removed on purpose | author decision |
| Cartoon mode (ink outlines, flat fills, the show's palette) | works; on by default, can be switched off in Settings | hardware |
| Other PSP models, NTSC discs | untested (PSP-1000 cannot run it: not enough RAM) | n/a |

## Hardware numbers (PSP-2000, tour build TEST62)

| Measure | Result |
|---|---|
| Tour finished to the end | yes; 0 faults, 0 stalls, 0 memory failures, 0 read errors |
| Frame rate, whole tour | median 28 fps (capped at 30) |
| Seconds under 20 fps | 6 to 9 percent, mostly in city driving on levels 3 to 6 |
| Frame time p95 by scene | 23 to 43 ms; driving scenes on levels 3 to 7 sit at 33.5 to 36.8 ms (30 fps is 33.3 ms) |
| Worst single frames | 212 to 263 ms when leaving the house at the start of levels 4 and 7 (the world is set up in that frame) |
| Streaming | 2162 cells loaded, worst request-to-ready delay 877 ms |
| Memory | lowest free heap 3.97 MB, lowest largest block 1.00 MB |
| Audio | 1014 s, 0 late buffers |
| Level load | 5.3 to 6.9 s per level in the tour |

## Known problems

- Driving in the city on levels 3 to 7 does not hold 30 fps and dips under 20 fps in places.
- Far-distance flicker is not solved. The fix for it hid the horizon on one level, so it is switched off in the final build.
- A "go home" icon can stay on screen after a level change; six reproduction paths did not trigger it, so the build logs extra state for the next report.
- A menu left open can leak into the next level. Seen once in a scripted tour (booth background carried from level 7 to level 2).
- Long play sessions on hardware have not been tested for memory fragmentation. Early builds hung after many level changes; the known leaks are closed.

## Not verified

PSP-3000 and Go; NTSC discs; sleep and wake; a full memory card; a corrupt save on hardware; a slow memory card; the ending to the credits on hardware; every cutscene on hardware; the bonus game on hardware.

## Reports

A bug report with the map code from the bottom left of the pause screen (for example L1 K9-7) is the most useful thing you can send. Reports from other PSP models and NTSC discs help the most.
