#!/bin/bash
# Data phase of ship.sh, sourced with ROOT/STAGE/LOG and ship functions.
# Kept separate so the gate executes the production loop without EBOOT/deploy.
RULES=(); while IFS= read -r l; do RULES+=("$l"); done < <(tools/ship_files.sh --rules)
FILES=(); NEWDATA=()
for r in "${RULES[@]}"; do
  IFS='|' read -r name path deps cmd <<< "$r"
  name=$(echo $name); path=$(echo $path); cmd=$(echo "$cmd" | sed 's/^ *//')
  deps=${deps//\{stage\}/$STAGE}   # dependencies produced earlier in this same staging transaction
  FILES+=("$name")
  mkdir -p "$STAGE/$(dirname "$name")" "$LOG/$(dirname "$name")" || fail "папка данных $name"
  src=""; for u in "${USE[@]:-}"; do [ "${u%%=*}" = "$name" ] && src="${u#*=}"; done
  if [ -n "$src" ]; then
    [ -f "$src" ] || fail "--use: нет файла $src"
    cp -c "$src" "$STAGE/$name" 2>/dev/null || cp "$src" "$STAGE/$name" || fail "копирование $name"; NEWDATA+=("$name=$path"); step "$name = $src (как есть)"; continue
  fi
  if [ "${SHIP_STAGE_OLD:-0}" != 1 ] && python tools/ship_cache.py check "$STAGE/$name" --deps "$deps" --cmd "$cmd" >/dev/null; then
    NEWDATA+=("$name=$path"); step "$name: проверенный результат этой staging-фазы"; continue
  fi
  why=""
  [ -f "$path" ] || why="нет файла"
  [ -z "$why" ] && [ "$name" = level.shr ] && [ $FORCE_LEVEL = 1 ] && why="--level"
  if [ -z "$why" ]; then
    if [ "${SHIP_HASH_OLD:-0}" = 1 ]; then
      for d in $deps; do [ "$d" -nt "$path" ] && { why="$d новее"; break; }; done
    else
      why=$(python tools/ship_cache.py check "$path" --deps "$deps" --cmd "$cmd"); hash_rc=$?
      [ "$hash_rc" != 2 ] || fail "$name: $why"
    fi
  fi
  if [ -z "$why" ]; then cp -c "$path" "$STAGE/$name" 2>/dev/null || cp "$path" "$STAGE/$name" || fail "копирование $name"; continue; fi
  # №880 (сборка с чистого клона): необязательное правило (команда true — файл кладёт отдельная сборка: far_plain, мультик) без файла — пропуск, не ошибка
  if [[ "$cmd" =~ ^true([[:space:]]|$) ]] && [ ! -f "$path" ]; then step "$name: необязательный, файла нет — пропуск"; continue; fi
  case "$name" in level.shr|l[0-9]/level.shr) quality_check ;; esac
  step "$name: пересборка ($why)"
  tmp="$STAGE/tmp_$name"; outdir="$tmp/$(dirname "$name")"
  mkdir -p "$outdir" || fail "временная папка $name"
  c=${cmd//\{out\}/$tmp/$name}; c=${c//\{outdir\}/$outdir}
  c=${c//\{stage\}/$STAGE}
  bash -c "$c" > "$LOG/$name.txt" 2>&1 || fail "экспорт $name: $(grep -v '^\s*$' "$LOG/$name.txt" | tail -1)"
  if [ ! -s "$tmp/$name" ] && grep -q '^НЕОБЯЗАТЕЛЬНО: пропуск' "$LOG/$name.txt"; then step "$name: $(grep -m1 '^НЕОБЯЗАТЕЛЬНО' "$LOG/$name.txt")"; rm -rf "$tmp"; continue; fi   # №880: экспортёр сам сказал «необязательно» (нет Blender)
  [ -s "$tmp/$name" ] || fail "экспорт $name: файл не появился ($c)"
  # A successful batch exporter may write multiple declared outputs (audio SAB + SAP).
  # Preserve only siblings with identical command/dependencies and the same output folder.
  case "$cmd" in *'{outdir}'*) ship_batch=1 ;; *) ship_batch=0 ;; esac
  if [ "$ship_batch" = 1 ] && [ "${SHIP_SIBLINGS_OLD:-0}" != 1 ]; then
    for sibling in "${RULES[@]}"; do
      IFS='|' read -r sn sp sd sc <<< "$sibling"
      sn=$(echo $sn); sd=$(echo $sd); sc=$(echo "$sc" | sed 's/^ *//'); sd=${sd//\{stage\}/$STAGE}
      [ "$sn" != "$name" ] && [ "$(dirname "$sn")" = "$(dirname "$name")" ] && [ "$sc" = "$cmd" ] && [ "$sd" = "$(echo $deps)" ] || continue
      generated="$outdir/$(basename "$sn")"
      [ -s "$generated" ] || continue
      cp -c "$generated" "$STAGE/$sn" 2>/dev/null || cp "$generated" "$STAGE/$sn" || fail "sideproduct $sn"
      python tools/ship_cache.py record "$STAGE/$sn" --deps "$deps" --cmd "$cmd" || fail "sideproduct hash $sn"
    done
  fi
  mv "$tmp/$name" "$STAGE/$name"; rm -rf "$tmp"; NEWDATA+=("$name=$path")
  python tools/ship_cache.py record "$STAGE/$name" --deps "$deps" --cmd "$cmd" || fail "хеш готового $name"
  step "$name собран"
done
