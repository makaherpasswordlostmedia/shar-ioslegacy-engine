#!/bin/bash
# TEST25: сборка выпускной конфигурации (SHAR_RELEASE + KEEP_DIAG + KEEP_HUD, без KEEP_SMOKE) и набор замены к карте TEST23.
# tools/test25_set.sh  ->  build/test25 (EBOOT, BUILD_INFO), build/test25set (EBOOT + pv2s.shr L2–L7 + звук L2/L5 + ЗАМЕНА.txt), build/test25set/SHA.txt (сверка с картой)
set -e
cd "$(dirname "$0")/.."
export PSPDEV="$HOME/Downloads/shar-psp/pspdev" PATH="$HOME/Downloads/shar-psp/pspdev/bin:$PATH"
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "рабочая копия не чистая: собирать только из коммитов"; git status --short | grep -v '^??'; exit 1; }
cmake --build viewer/build_t25 2>&1 | grep -E "error|Built target" || true
EBOOT_SRC=viewer/build_t25/EBOOT.PBP tools/pack_test.sh "SHAR TEST25" build/test25
sed -i '' 's|^флаги сборки:.*|флаги сборки: SHAR_RELEASE=ON SHAR_RELEASE_KEEP_DIAG=ON SHAR_RELEASE_KEEP_HUD=ON (как игра у игрока: без сценария и журнала смоука; чёрный ящик фоном; счётчик виден; STAT10 раз в 10 с в ящик)|' build/test25/BUILD_INFO.txt
S=build/test25set; D=$S/PSP/GAME/SHARTEST15; rm -rf $S; mkdir -p $D
cp build/test25/PSP/GAME/SHARTEST15/EBOOT.PBP $D/
for n in 2 3 4 5 6 7; do mkdir -p $D/l$n; cp build/far2_out/l$n/pv2s.shr $D/l$n/; done
for n in 2 5; do mkdir -p $D/l$n/audio; cp build/audio25/l$n/audio/sfx.sab build/audio25/l$n/audio/music.sap $D/l$n/audio/; done
cp build/test25/BUILD_INFO.txt $S/
cat > $S/ЗАМЕНА.txt <<'T'
ЗАМЕНА TEST25 к карте с TEST23 (EBOOT f11ef883): EBOOT.PBP (выпускная конфигурация), l2..l7/pv2s.shr (новые, PVS по курсу), l2/audio и l5/audio (музыка клуба №593).
Убрать с карты из PSP/GAME/SHARTEST15 (в резерв): scenario.txt, smokelog (иначе режим служебный: нет камер въезда и подсказок Барта). Остальное без изменений.
T
( cd $D && find . -type f | sort | while read f; do printf "%s  %s  карта:%s\n" "$(shasum -a 256 "$f" | cut -c1-8)" "$f" "$( [ -f /Volumes/PSP/PSP/GAME/SHARTEST15/$f ] && shasum -a 256 /Volumes/PSP/PSP/GAME/SHARTEST15/$f | cut -c1-8 || echo нет)"; done ) > $S/SHA.txt
cat $S/SHA.txt
