#!/bin/sh
# Install both merged databases from one pinned GitHub release.
set -eu
umask 077

REPO="${GEODATA_REPO:-shveetsov/xray-rules}"
TARGET="${MIHOMO_HOME:-/opt/etc/mihomo}"
STAGE=""
INSTALLED=0
RESTART_NEEDED=0
HAD_SITE=0
HAD_IP=0

log() { printf '[geodata] %s\n' "$*"; }
fail() { log "ОШИБКА: $*" >&2; exit 1; }

for tool in curl yq sha256sum mihomo xkeen pidof; do
    command -v "$tool" >/dev/null 2>&1 || fail "Не найдена команда $tool"
done
[ -s "$TARGET/config.yaml" ] || fail "Сначала сохраните config.yaml в $TARGET"
mkdir -p "$TARGET"
LOCK="$TARGET/.geodata-update.lock"
mkdir "$LOCK" 2>/dev/null || fail "Обновление уже выполняется (или остался $LOCK после отключения питания)"

cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    set +e
    restore_failed=0
    if [ "$INSTALLED" -eq 1 ]; then
        log "Восстанавливаем предыдущие базы."
        if [ "$HAD_SITE" -eq 1 ]; then
            cp -p "$STAGE/previous/GeoSite.dat" "$TARGET/GeoSite.dat" || restore_failed=1
        else
            rm -f "$TARGET/GeoSite.dat" || restore_failed=1
        fi
        if [ "$HAD_IP" -eq 1 ]; then
            cp -p "$STAGE/previous/GeoIP.dat" "$TARGET/GeoIP.dat" || restore_failed=1
        else
            rm -f "$TARGET/GeoIP.dat" || restore_failed=1
        fi
        if [ "$restore_failed" -eq 1 ]; then
            log "Откат неполный; резервные файлы сохранены в $STAGE/previous"
            result=1
        elif [ "$RESTART_NEEDED" -eq 1 ]; then
            xkeen -restart || log "Не удалось запустить прежнюю конфигурацию; проверьте XKeen."
        fi
    fi
    if [ "$restore_failed" -eq 0 ] && [ -n "$STAGE" ]; then rm -rf "$STAGE"; fi
    rmdir "$LOCK" 2>/dev/null || true
    exit "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

STAGE=$(mktemp -d "$TARGET/.geodata-stage.XXXXXX")
curl -fLsS --retry 2 --connect-timeout 15 --max-time 120 \
    "https://api.github.com/repos/$REPO/releases/latest" -o "$STAGE/release.json"
TAG=$(yq -r '.tag_name // ""' "$STAGE/release.json")
case "$TAG" in
    ''|*[!a-zA-Z0-9._-]*) fail "Некорректный тег релиза" ;;
esac
BASE="https://github.com/$REPO/releases/download/$TAG"
log "Загружаем базы из релиза $TAG."
for name in GeoSite.dat GeoIP.dat SHA256SUMS; do
    curl -fLsS --retry 2 --connect-timeout 15 --max-time 300 "$BASE/$name" -o "$STAGE/$name"
    [ -s "$STAGE/$name" ] || fail "Пустой файл $name"
done
awk '$2 == "GeoSite.dat" || $2 == "GeoIP.dat" {print}' "$STAGE/SHA256SUMS" > "$STAGE/checksums"
[ "$(wc -l < "$STAGE/checksums" | tr -d ' ')" -eq 2 ] || fail "В SHA256SUMS отсутствует пара баз"
for name in GeoSite.dat GeoIP.dat; do
    count=$(awk -v name="$name" '$2 == name {n++} END {print n+0}' "$STAGE/checksums")
    [ "$count" -eq 1 ] || fail "В SHA256SUMS отсутствует единственная запись $name"
done
(cd "$STAGE" && sha256sum -c checksums) || fail "Не совпали контрольные суммы"

# -t parses configuration without opening listeners or the runtime cache DB.
log "Проверяем новые базы с вашей конфигурацией Mihomo."
SSL_CERT_FILE="${SSL_CERT_FILE:-/opt/etc/ssl/certs/ca-certificates.crt}" \
    mihomo -t -d "$STAGE" -f "$TARGET/config.yaml" || fail "Mihomo отклонил новые базы; рабочие файлы сохранены"
# Initialization can download a default database when a supplied file is bad.
# Only the exact release files that passed checksums may be installed.
(cd "$STAGE" && sha256sum -c checksums) || fail "При проверке Mihomo изменил скачанные базы"

if [ -s "$TARGET/GeoSite.dat" ] && [ -s "$TARGET/GeoIP.dat" ] && \
    cmp -s "$STAGE/GeoSite.dat" "$TARGET/GeoSite.dat" && \
    cmp -s "$STAGE/GeoIP.dat" "$TARGET/GeoIP.dat"; then
    log "Базы не изменились; перезапуск не требуется."
    exit 0
fi

mkdir "$STAGE/previous"
if [ -f "$TARGET/GeoSite.dat" ]; then cp -p "$TARGET/GeoSite.dat" "$STAGE/previous/GeoSite.dat"; HAD_SITE=1; fi
if [ -f "$TARGET/GeoIP.dat" ]; then cp -p "$TARGET/GeoIP.dat" "$STAGE/previous/GeoIP.dat"; HAD_IP=1; fi
INSTALLED=1
mv "$STAGE/GeoSite.dat" "$TARGET/GeoSite.dat"
mv "$STAGE/GeoIP.dat" "$TARGET/GeoIP.dat"
RESTART_NEEDED=1
xkeen -restart || fail "XKeen не запустился с новыми базами"
pidof mihomo >/dev/null 2>&1 || fail "После перезапуска процесс Mihomo не найден"
INSTALLED=0
log "Готово: GeoSite.dat и GeoIP.dat обновлены, Mihomo запущен."
