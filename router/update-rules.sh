#!/bin/sh
# Обновление правил xray-rules с GitHub
# Размести на роутере: /opt/etc/xray/update-rules.sh
# Права: chmod +x /opt/etc/xray/update-rules.sh

REPO="shveetsov/xray-rules"
BASE_URL="https://github.com/${REPO}/releases/latest/download"
GEO_DIR="/opt/etc/xray/dat"

log() {
  echo "[update-rules] $1"
}

mkdir -p "${GEO_DIR}"

log "Обновляем сам скрипт..."
curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/router/update-rules.sh" \
  -o "${0}.tmp" && mv "${0}.tmp" "${0}" && chmod +x "${0}" \
  || log "Не удалось обновить скрипт, продолжаем со старой версией"

log "Скачиваем geosite_shvetsov.dat..."
curl -fsSL "${BASE_URL}/geosite_shvetsov.dat" -o "${GEO_DIR}/geosite_shvetsov.dat.tmp" \
  || { log "ОШИБКА: geosite"; exit 1; }

log "Скачиваем geoip_shvetsov.dat..."
curl -fsSL "${BASE_URL}/geoip_shvetsov.dat" -o "${GEO_DIR}/geoip_shvetsov.dat.tmp" \
  || { log "ОШИБКА: geoip"; exit 1; }

# Атомарная замена — только если оба файла скачаны успешно
mv "${GEO_DIR}/geosite_shvetsov.dat.tmp" "${GEO_DIR}/geosite_shvetsov.dat"
mv "${GEO_DIR}/geoip_shvetsov.dat.tmp"   "${GEO_DIR}/geoip_shvetsov.dat"

log "Файлы обновлены. Перезапускаем XKeen..."
xkeen -restart

log "Готово."
