#!/usr/bin/env bash
# Загрузка расширения в базу с конфигурацией «Склад: обмен с маркетплейсом».
#   scripts/build.sh <каталог базы>
set -euo pipefail

IB=$(realpath "${1:?каталог базы}")
cd "$(dirname "$0")/.."
V8=${V8:-$(ls -d /opt/1cv8/x86_64/*/ | sort -V | tail -1)}
EXT=РаспознаваниеДокументов

if ! "$V8/ibcmd" extension info --db-path="$IB" --name="$EXT" >/dev/null 2>&1; then
  "$V8/ibcmd" extension create --db-path="$IB" --name="$EXT" --name-prefix=рд_ --purpose=add-on
fi
# Безопасный режим запрещает HTTP-запросы к сервису извлечения текста и к модели
"$V8/ibcmd" extension update --db-path="$IB" --name="$EXT" --safe-mode=no --unsafe-action-protection=no
"$V8/ibcmd" infobase config import --db-path="$IB" --extension="$EXT" src
"$V8/ibcmd" infobase config apply --db-path="$IB" --extension="$EXT" --force

LOG=$(mktemp)
if ! "$V8/1cv8" DESIGNER /F "$IB" /DisableStartupDialogs /DisableStartupMessages \
     /CheckModules -ThinClient -Server -Extension "$EXT" /Out "$LOG"; then
  cat "$LOG"; rm -f "$LOG"; exit 1
fi
rm -f "$LOG"
echo "Расширение $EXT загружено в $IB"
