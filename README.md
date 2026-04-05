# xray-rules

Единый набор правил для нескольких Keenetic/XKeen роутеров.

## Структура

- `geosite/data/all` — единый список доменов для сборки `geosite_shvetsov.dat`
- `geoip/data/all.txt` — единый список IP/CIDR
- `router/05_routing.json` — шаблон маршрутизации для XKeen
- `.github/workflows/build.yml` — GitHub Actions для сборки артефактов
- `.gitignore` — исключения для мусорных и локальных файлов

## Что сейчас собирается

GitHub Actions собирает:

- `geosite_shvetsov.dat`
- копию `geoip/data/all.txt`
- `05_routing.json`
- `README.md`

## Что сейчас используется в routing

В `05_routing.json` используются:

- `ext:geosite_shvetsov.dat:all`
- локально прописанные IP/CIDR из `geoip/data/all.txt`

Это сделано специально, чтобы конфигурация не зависела от сторонних `geosite_*.dat` и `geoip_*.dat`.

## Как обновлять роутер

1. Скачать artifact из GitHub Actions
2. Скопировать `geosite_shvetsov.dat` в каталог ресурсов Xray на роутере
3. Заменить `05_routing.json`
4. Перезапустить XKeen

## Команды на роутере

```sh
xkeen -stop
xkeen -start
```

или

```sh
xkeen -restart
```

## Следующий этап

Когда базовая схема стабильно заработает на всех роутерах, можно добавить сборку собственного `geoip_shvetsov.dat`, чтобы убрать IP/CIDR из `05_routing.json` и подключать их через:

```json
"ext:geoip_shvetsov.dat:all"
```