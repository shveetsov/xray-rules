#!/bin/sh
# Обновление правил xray-rules с GitHub
# Размести на роутере: /opt/etc/xray/update-rules.sh
# Права: chmod +x /opt/etc/xray/update-rules.sh

REPO="shveetsov/xray-rules"
BASE_URL="https://github.com/${REPO}/releases/latest/download"
GEO_DIR="/opt/share/xray"

log() {
  echo "[update-rules] $1"
}

log "Скачиваем geosite_shvetsov.dat..."
wget -q --show-progress -O "${GEO_DIR}/geosite_shvetsov.dat.tmp" \
  "${BASE_URL}/geosite_shvetsov.dat" || { log "ОШИБКА: geosite"; exit 1; }

log "Скачиваем geoip_shvetsov.dat..."
wget -q --show-progress -O "${GEO_DIR}/geoip_shvetsov.dat.tmp" \
  "${BASE_URL}/geoip_shvetsov.dat" || { log "ОШИБКА: geoip"; exit 1; }

# Атомарная замена — только если оба файла скачаны успешно
mv "${GEO_DIR}/geosite_shvetsov.dat.tmp" "${GEO_DIR}/geosite_shvetsov.dat"
mv "${GEO_DIR}/geoip_shvetsov.dat.tmp"   "${GEO_DIR}/geoip_shvetsov.dat"

log "Файлы обновлены. Перезапускаем XKeen..."
xkeen -restart

log "Готово."
