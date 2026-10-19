# xray-rules

Сборка геобаз для Keenetic/XKeen с Mihomo и Xray. На роутер загружается одна база доменов `GeoSite.dat` и одна база IP `GeoIP.dat`. Каждая содержит три стандартных источника XKeen и собственные списки.

## Источники и категории

| Префикс | Домены | IP |
|---|---|---|
| `v2fly-` | [V2Fly domain-list-community](https://github.com/v2fly/domain-list-community) | [Loyalsoldier v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) |
| `refilter-` | [Re:filter](https://github.com/1andrevich/Re-filter-lists) | тот же репозиторий |
| `zkeen-` | [ZKeen Domains](https://github.com/jameszeroX/zkeen-domains) | [ZKeen IP](https://github.com/jameszeroX/zkeen-ip) |
| `shvetsov-` | `geosite/data/all` | `geoip/data/all.txt` |

Ваши записи сохраняются в исходных файлах как есть. В итоговых базах их категория называется **`shvetsov-all`**. Например, `v2fly-youtube` и `zkeen-youtube` — два отдельных списка, их содержимое не смешивается. Все названия и количества записей публикуются в `categories.md` каждого релиза.

Исходники и адреса загрузки задаются в `sources.json`. Скрипт меняет только имя категории, сохраняя типы сопоставления доменов, регулярные выражения, атрибуты и CIDR. Категории с `reverse_match=true`, которые Mihomo не учитывает, отклоняются при сборке. Служебный псевдоним `cn` указывает на `v2fly-cn`: Mihomo проверяет его при загрузке геобаз.

## Что публикуется

GitHub Actions запускается при изменениях в `main`/`master`, вручную и ежедневно около **03:17 по Камчатке (15:17 UTC)**. Запуск по расписанию может задерживаться на стороне GitHub.

| Файл релиза | Назначение |
|---|---|
| `GeoSite.dat` | Все четыре источника доменов с префиксами |
| `GeoIP.dat` | Все четыре источника IP с префиксами |
| `categories.md` | Полный каталог доступных категорий |
| `manifest.json` | Версии источников, SHA-256, размеры и состав баз |
| `SHA256SUMS` | Контрольные суммы файлов релиза |
| `mihomo-rules.yaml` | Перенос прежней выборочной маршрутизации на новые категории |
| `update-mihomo-geodata.sh` | Проверка и обновление пары баз на роутере |
| `geosite_shvetsov.dat`, `geoip_shvetsov.dat` | Прежние отдельные пользовательские базы с категорией `all` для существующих Xray |
| `05_routing.json`, `update-rules.sh` | Прежняя конфигурация и загрузчик Xray |

Для каждого источника выбирается конкретный релиз. Внутри сборки пара Re:filter скачивается из одного релиза. Перед публикацией все категории проверяются настоящим Mihomo 1.19.32.

Ссылки на две итоговые базы:

```text
https://github.com/shveetsov/xray-rules/releases/latest/download/GeoSite.dat
https://github.com/shveetsov/xray-rules/releases/latest/download/GeoIP.dat
```

Они появятся после push этих изменений и первой успешной сборки.

## Настройка Mihomo на роутере

1. Сделайте резервную копию текущего `/opt/etc/mihomo/config.yaml`.
2. Сохраните в конфиге свои `listeners` и `proxy-providers` со ссылкой подписки и постоянным HWID.
3. Настройки режима, геобаз, сниффинга, `proxy-groups` и `rules` возьмите из `router/mihomo-rules.yaml`. Каждый ключ верхнего уровня должен встречаться один раз. Пример использует провайдер `subscription_1` и группу `AUTO`.
4. Обязательно сохраните `geodata-mode: true` и `geo-auto-update: false`, чтобы встроенное обновление Mihomo не заменило объединённые базы стандартными.
5. Сохраните конфиг на диск, пока без применения: сначала нужно загрузить базы с новыми именами категорий.
6. В Linux-shell роутера (`ssh admin@router`, затем `exec sh`) установите и запустите загрузчик:

```sh
curl -fLsS https://raw.githubusercontent.com/shveetsov/xray-rules/main/router/update-mihomo-geodata.sh \
  -o /opt/etc/mihomo/update-geodata.sh
chmod 700 /opt/etc/mihomo/update-geodata.sh
/opt/etc/mihomo/update-geodata.sh
```

Загрузчик фиксирует тег релиза, скачивает обе базы, проверяет SHA-256 и запускает `mihomo -t` с новыми файлами и вашей сохранённой конфигурацией. Затем устанавливает базы и перезапускает XKeen. При ошибке загрузки/проверки рабочие базы сохраняются; при ошибке перезапуска восстанавливается предыдущая пара. Если файлы не изменились, перезапуска нет. Скрипт требует `curl`, `yq`, `sha256sum`, Mihomo и XKeen.

Примеры выборки внутри объединённых баз:

```yaml
rules:
  - GEOSITE,v2fly-youtube,AUTO
  - GEOSITE,v2fly-openai,AUTO
  - GEOSITE,shvetsov-all,AUTO
  - GEOIP,v2fly-telegram,AUTO
  - GEOIP,shvetsov-all,AUTO
  - MATCH,DIRECT
```

Это сокращённый пример. `router/mihomo-rules.yaml` также сохраняет прежние локальные исключения и блокировки UDP 135/137/138/139 и UDP 443. Парные правила REJECT после AUTO защищают от прямого выхода UDP при узле без поддержки UDP.

Подписка и геобазы обновляются независимо. Для подписки оставьте `proxy-providers.subscription_1.interval: 3600`, а для проверок серверов — интервал 60 секунд и `lazy: false`. В `port_exclude` XKeen остаются 1701, 500, 4500, 50; `port_proxying` без активных записей.

Для ежедневной проверки новых баз добавьте в существующий crontab роутера одну строку (04:00 в часовом поясе роутера):

```cron
0 4 * * * /opt/etc/mihomo/update-geodata.sh >> /opt/var/log/update-geodata.log 2>&1
```

Обновления баз через прежний `xkeen -ug` не должны перезаписывать эти два файла Mihomo. Используйте один загрузчик объединённых баз.

## Редактирование списков и локальная сборка

Редактируйте `geosite/data/all` и `geoip/data/all.txt`, затем сделайте push. Сами записи при переходе на объединённые базы не менялись.

Для сборки на Mac/Linux нужны Python 3.10+, Go и Git. Дополнительные Python-пакеты не требуются:

```sh
python3 -m unittest discover -s tests -v
python3 tools/build.py
```

Скрипт скачает официальные компиляторы V2Fly и текущие upstream-базы. Результат — `dist/`, служебные файлы — `.cache/`. Ревизии компиляторов записываются в `manifest.json`; для получения новых версий удалите `.cache/tools/` перед следующей сборкой.

Проверка всех категорий своим бинарником Mihomo:

```sh
python3 tools/check_mihomo.py --binary /path/to/mihomo --dist dist
```

Для повторной сборки из уже скачанных баз передайте `--upstream-dir /path/to/dat-files`. В каталоге должны лежать `v2fly-geosite.dat`, `v2fly-geoip.dat`, `refilter-geosite.dat`, `refilter-geoip.dat`, `zkeen-geosite.dat`, `zkeen-geoip.dat`. Без этого аргумента базы загружаются заново при каждой сборке.

## Совместимость с прежними Xray

Существующий `router/update-rules.sh` продолжает скачивать только `geosite_shvetsov.dat` и `geoip_shvetsov.dat`; ссылки `ext:geosite_shvetsov.dat:all` и `ext:geoip_shvetsov.dat:all` сохраняются.

Объединённые файлы тоже подходят для Xray, с новыми именами категорий:

```json
{
  "domain": ["ext:GeoSite.dat:v2fly-youtube", "ext:GeoSite.dat:shvetsov-all"],
  "ip": ["ext:GeoIP.dat:shvetsov-all"]
}
```
