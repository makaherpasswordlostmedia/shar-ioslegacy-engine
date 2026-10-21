#!/bin/sh
# Расписание ночи ботов на Маке (Т1.6): launchd-задание ua.heartbeat.shar-bots-night — каждый день в 23:00
# tools/bots/night_launchd.sh (он же Ночь.command до 07:00, только от сети, без Claude и API).
#   sh tools/bots/night_schedule.sh install     поставить (и перезаписать)
#   sh tools/bots/night_schedule.sh remove      выключить совсем
#   sh tools/bots/night_schedule.sh status      есть ли в launchctl list
#   sh tools/bots/night_schedule.sh test HH:MM UNTIL [battery]   пробное задание ua.heartbeat.shar-bots-night-test на HH:MM (ночь до UNTIL;
#                                                  battery — контроль гейта: «Мак от батареи», ночь не начинается)
cd "$(dirname "$0")/../.." || exit 1
ROOT="$PWD"; UIDN=$(id -u); LA="$HOME/Library/LaunchAgents"
# launchd не пускает фоновый /bin/sh в ~/Downloads (защита папок macOS): задание открывает .command Терминалом —
# как двойной клик, окно ночи видно. Пробный запуск — свой .command в build/bots с аргументами.
plist() {   # $1 метка, $2 час, $3 минута, $4 .command
  L="$1"; H="$2"; M="$3"; CMD="$4"
  cat > "$LA/$L.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$L</string>
<key>ProgramArguments</key><array><string>/usr/bin/open</string><string>-a</string><string>Terminal</string><string>$CMD</string></array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>$H</integer><key>Minute</key><integer>$M</integer></dict>
<key>StandardOutPath</key><string>$HOME/Library/Logs/shar-bots-night.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/shar-bots-night.log</string>
<key>ProcessType</key><string>Background</string>
</dict></plist>
P
  launchctl bootout "gui/$UIDN/$L" 2>/dev/null; launchctl bootstrap "gui/$UIDN" "$LA/$L.plist"
}
case "$1" in
  install) plist ua.heartbeat.shar-bots-night 23 0 "$ROOT/tools/bots/Ночь-по-расписанию.command"; launchctl list | grep shar-bots-night ;;
  remove) launchctl bootout "gui/$UIDN/ua.heartbeat.shar-bots-night" 2>/dev/null; rm -f "$LA/ua.heartbeat.shar-bots-night.plist"; echo "снято" ;;
  status) launchctl list | grep shar-bots-night || echo "нет задания" ;;
  test) H=${2%%:*}; M=${2##*:}; T="$ROOT/build/bots/night-test.command"; FB=""; [ "$4" = battery ] && FB="NIGHT_FAKE_BATTERY=1 "
        printf '#!/bin/sh\n# пробный запуск Т1.6 (night_schedule.sh test)\ncd "%s" || exit 1\n%sNIGHT_ANY_TIME=1 NIGHT_SUFFIX=-test NIGHT_HARD_STOP=%s sh tools/bots/night_launchd.sh --until %s 2>&1 | tee -a "$HOME/Library/Logs/shar-bots-night.log"\nexit\n' "$ROOT" "$FB" "$(date -j -v+3M -f %H:%M "$3" +%H:%M)" "$3" > "$T"; chmod +x "$T"
        plist ua.heartbeat.shar-bots-night-test "$((10#$H))" "$((10#$M))" "$T"; launchctl list | grep shar-bots-night-test ;;
  test-remove) launchctl bootout "gui/$UIDN/ua.heartbeat.shar-bots-night-test" 2>/dev/null; rm -f "$LA/ua.heartbeat.shar-bots-night-test.plist" ;;
  *) sed -n 2,8p "$0" ;;
esac
