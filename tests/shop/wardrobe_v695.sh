#!/bin/bash
# №695 (гардероб: лучи вместо голубого пятна, модель выше, подписи кнопок и шрифт названия как у будки): гейт данных.
#   зелёный: с флагами отката WARDROBE_TYPO_OLD=1 WARDROBE_BG_OLD=1 WARDROBE_LAYOUT_OLD=1 пакет и skins.txt побайтно прежние (sha в EXPECT_OLD),
#            по умолчанию пакет другой, строка view выше на 7 px; в пакете нет пятна Spotlight
#   красный контроль: тот же гейт с отключённым откатом (флаги не заданы) обязан показать «другой» — иначе гейт ничего не проверяет
set -u
cd "$(dirname "$0")/../.."; . .venv/bin/activate
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
EXPECT_OLD=${EXPECT_OLD:-660fa9fe9310}
WARDROBE_RAYBAKE_OLD=1 WARDROBE_TYPO_OLD=1 WARDROBE_BG_OLD=1 python tools/skins_export.py --ui $T/old.shr >/dev/null || exit 1
WARDROBE_LAYOUT_OLD=1 python tools/skins_export.py --list $T/old.txt >/dev/null || exit 1
WARDROBE_RAYBAKE_OLD=1 python tools/skins_export.py --ui $T/new.shr >/dev/null || exit 1
python tools/skins_export.py --list $T/new.txt >/dev/null || exit 1
so=$(shasum $T/old.shr | cut -c1-12); sn=$(shasum $T/new.shr | cut -c1-12)
yo=$(grep '^view' $T/old.txt | awk '{print $3}'); yn=$(grep '^view' $T/new.txt | awk '{print $3}')
fail=0
[ "$so" = "$EXPECT_OLD" ] || { echo "FAIL откат пакета: $so != $EXPECT_OLD"; fail=1; }
[ "$sn" != "$so" ] || { echo "FAIL по умолчанию пакет не изменился"; fail=1; }
[ "$(echo "$yo - $yn" | bc)" = "7.0" ] || { echo "FAIL view: $yo -> $yn, нужно -7"; fail=1; }
[ $fail = 0 ] && echo "PASS wardrobe_v695: откат побайтно ($so), новый пакет $sn, view $yo -> $yn"
exit $fail
