# xray-rules

Единый набор правил для нескольких Keenetic/XKeen роутеров.

## Структура

| Файл | Назначение |
|------|-----------|
| `geosite/data/all` | Список доменов → `geosite_shvetsov.dat` |
| `geoip/data/all.txt` | Список IP/CIDR → `geoip_shvetsov.dat` |
| `router/05_routing.json` | Конфигурация маршрутизации XKeen |
| `router/update-rules.sh` | Скрипт автообновления на роутере |
| `.github/workflows/build.yml` | GitHub Actions: сборка и публикация |

## Что собирается

При каждом push в `main` GitHub Actions автоматически:

1. Компилирует `geosite_shvetsov.dat` из `geosite/data/all`
2. Компилирует `geoip_shvetsov.dat` из `geoip/data/all.txt`
3. Публикует оба файла как **GitHub Release** с тегом `latest`

Прямые ссылки для скачивания:

```
https://github.com/shveetsov/xray-rules/releases/latest/download/geosite_shvetsov.dat
https://github.com/shveetsov/xray-rules/releases/latest/download/geoip_shvetsov.dat
https://github.com/shveetsov/xray-rules/releases/latest/download/05_routing.json
```

## Что используется в routing

В `05_routing.json`:

- `ext:geosite_shvetsov.dat:all` — домены для проксирования
- `ext:geoip_shvetsov.dat:all` — IP/CIDR для проксирования

## Автообновление на роутере

### Первичная установка (один раз)

Выполнить прямо на роутере в SSH-консоли:

```sh
curl -fsSL https://raw.githubusercontent.com/shveetsov/xray-rules/main/router/update-rules.sh \
  -o /opt/etc/xray/update-rules.sh \
  && chmod +x /opt/etc/xray/update-rules.sh \
  && /opt/etc/xray/update-rules.sh
```

### Автозапуск по расписанию (cron)

```sh
sudo crontab -e
```

Добавить строку (обновление каждый день в 04:00):

```
0 3 * * * /opt/etc/xray/update-rules.sh >> /opt/var/log/update-rules.log 2>&1
```

### Ручное обновление

```sh
/opt/etc/xray/update-rules.sh
```

## Как обновить правила

1. Отредактировать `geosite/data/all` или `geoip/data/all.txt`
2. Сделать push в `main`
3. GitHub Actions соберёт и опубликует новый Release
4. Роутер подтянет обновление по cron в 04:00 (или запустить вручную)

## Команды XKeen на роутере

```sh
xkeen -restart
```
