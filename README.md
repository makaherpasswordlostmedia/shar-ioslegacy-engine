# SHAR-PSP

Open-source native PSP engine for *The Simpsons: Hit & Run*. Not an emulator, not decompiled code.
Shared as groundwork for the community: take it, build it, improve it.

No game files are included. The game data is converted from your own PS2 disc.

## Contents

- `viewer/` the PSP engine (C, PSPSDK)
- `tools/` converter from the PS2 disc to PSP packages, build and test scripts (Python, shell)
- `tests/` regression tests
- `docs/typography/` UI typography settings used by the converter

Comments are mostly in Russian.

## Build

1. `./setup.sh` installs the PSPDEV toolchain into `./pspdev`
2. `export PSPDEV=$PWD/pspdev PATH=$PWD/pspdev/bin:$PATH`
3. `cd viewer && psp-cmake -S . -B build && cmake --build build` builds `EBOOT.PBP`

Game data: unpack your own disc with [hit-and-run-web](https://github.com/Vheissu/hit-and-run-web) into
`hit-and-run-web/source/`, run `tools/build_level.sh` / `tools/ship.sh`, copy the result next to the EBOOT
in `PSP/GAME/SHARVIEW`. Tested on a PSP-2000 with custom firmware.

## Reporting bugs

The pause screen shows a map code in the bottom-left corner (like `L1 K9-7`). Put it in your issue,
so anyone can find the exact spot.

## Credits and license

Based on [donut](https://github.com/plowteam/donut) (GPL-3.0) and
[hit-and-run-web](https://github.com/Vheissu/hit-and-run-web) by Dwayne Charrington (MIT).
The leaked source of the original game was never used. License: GPL-3.0.
The Simpsons and The Simpsons: Hit & Run are trademarks of their respective owners. Non-commercial fan project.
