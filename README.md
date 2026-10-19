# xray-rules

Объединённые базы доменов и IP-адресов для выборочной маршрутизации в Mihomo и Xray, в том числе на роутерах Keenetic с XKeen.
 
Проект собирает списки V2Fly, Re:filter, ZKeen и собственные записи в два файла: `GeoSite.dat` и `GeoIP.dat`. Категории каждого источника получают отдельный префикс, поэтому их можно использовать независимо в правилах маршрутизации.

## Состав баз

| Префикс категорий | Домены | IP-адреса |
|---|---|---|
| `v2fly-` | [V2Fly domain-list-community](https://github.com/v2fly/domain-list-community) | [Loyalsoldier v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) |
| `refilter-` | [Re:filter](https://github.com/1andrevich/Re-filter-lists) | [Re:filter](https://github.com/1andrevich/Re-filter-lists) |
| `zkeen-` | [ZKeen Domains](https://github.com/jameszeroX/zkeen-domains) | [ZKeen IP](https://github.com/jameszeroX/zkeen-ip) |
| `shvetsov-` | [Собственный список доменов](geosite/data/all) | [Собственный список IP-адресов](geoip/data/all.txt) |

Например, `v2fly-youtube` и `zkeen-youtube` — отдельные категории из разных источников. Собственные записи доступны в обеих базах под именем `shvetsov-all`.

Полный перечень категорий и количество записей в каждой публикуются в файле `categories.md` в составе релиза. Источники и служебные псевдонимы задаются в [sources.json](sources.json).

При объединении меняются имена категорий. Типы сопоставления доменов, регулярные выражения, атрибуты и IP-подсети сохраняются. Категории с `reverse_match=true` отклоняются при сборке, поскольку Mihomo не учитывает этот признак. Служебная категория `cn` дублирует `v2fly-cn` для проверки баз при запуске Mihomo.

## Загрузка

Готовые файлы доступны в [последнем релизе](https://github.com/shveetsov/xray-rules/releases/latest).

Прямые ссылки на объединённые базы:

- [GeoSite.dat — база доменов](https://github.com/shveetsov/xray-rules/releases/latest/download/GeoSite.dat)
- [GeoIP.dat — база IP-адресов](https://github.com/shveetsov/xray-rules/releases/latest/download/GeoIP.dat)

### Файлы релиза

| Файл | Назначение |
|---|---|
| `GeoSite.dat` | Объединённая база доменов из всех источников |
| `GeoIP.dat` | Объединённая база IP-адресов из всех источников |
| `categories.md` | Каталог категорий с количеством записей |
| `manifest.json` | Сведения о сборке, версиях источников, составе и контрольных суммах баз |
| `SHA256SUMS` | Контрольные суммы файлов релиза |
| `mihomo-rules.yaml` | Пример правил маршрутизации для Mihomo |
| `update-mihomo-geodata.sh` | Скрипт установки и обновления объединённых баз для Mihomo |
| `geosite_shvetsov.dat`, `geoip_shvetsov.dat` | Отдельные базы собственных списков с категорией `all` для существующих конфигураций Xray |
| `05_routing.json`, `update-rules.sh` | Пример маршрутизации и скрипт обновления отдельных баз для Xray |
| `README.md` | Документация проекта на момент сборки |

## Сборка и публикация

GitHub Actions запускает сборку:

- при изменении списков, конфигурации источников, скриптов или документации в ветках `main` и `master`;
- ежедневно в **15:17 UTC**;
- вручную через **Actions → Build geodata for Mihomo and Xray → Run workflow**.

Запуски по расписанию могут задерживаться на стороне GitHub. Условия запуска заданы в [build.yml](.github/workflows/build.yml).

При каждой сборке загружаются актуальные базы внешних источников и компилируются собственные списки. Для каждого репозитория фиксируется конкретный релиз, чтобы файлы из одного источника относились к одной версии. Перед публикацией выполняются тесты, а все категории проверяются с помощью Mihomo 1.19.32.

После успешной сборки создаётся GitHub Release. Роутер получает новые файлы при следующем запуске скрипта обновления — вручную или по расписанию.

## Использование с Mihomo на Keenetic

Для приведённых команд нужны Entware, XKeen, Mihomo, `curl`, `yq` из проекта `mikefarah/yq` и `sha256sum`. Команды выполняются в Linux-оболочке роутера. Отдельное ядро Xray для загрузки этих баз в Mihomo не требуется.

### Настройка конфигурации

1. Сохраните резервную копию `/opt/etc/mihomo/config.yaml`.
2. Добавьте настройки из [router/mihomo-rules.yaml](router/mihomo-rules.yaml) в существующий конфиг. Сохраните настроенные `listeners` и `proxy-providers`, включая ссылку подписки и заголовки провайдера. Каждый ключ верхнего уровня YAML должен встречаться один раз.
3. Согласуйте имена провайдера и группы с конфигурацией. В примере используются провайдер `subscription_1` и группа `AUTO` типа `fallback`.
4. Сохраните файл. Перед применением правил с новыми категориями установите объединённые базы по инструкции ниже.

Параметры геобаз в `config.yaml`:

```yaml
geodata-mode: true
geodata-loader: memconservative
geo-auto-update: false
```

Встроенное обновление геобаз Mihomo должно быть отключено: объединённую пару обновляет скрипт проекта.

Пример обращения к категориям в правилах:

```yaml
rules:
  - GEOSITE,v2fly-youtube,AUTO
  - GEOSITE,v2fly-openai,AUTO
  - GEOSITE,shvetsov-all,AUTO
  - GEOIP,v2fly-telegram,AUTO
  - GEOIP,shvetsov-all,AUTO
  - MATCH,DIRECT
```

Это сокращённый пример синтаксиса. В `router/mihomo-rules.yaml` также предусмотрены прямой доступ к локальным IP-адресам, блокировка UDP-портов 135, 137, 138, 139 и 443, а также правила `REJECT` после правил `AUTO`. Эти дополнительные правила предотвращают переход к прямому подключению для выбранных категорий, если узел не поддерживает UDP. Набор правил следует адаптировать под нужную схему маршрутизации.

### Установка и обновление баз

Установите скрипт и выполните первое обновление:

```sh
curl -fLsS https://raw.githubusercontent.com/shveetsov/xray-rules/main/router/update-mihomo-geodata.sh \
  -o /opt/etc/mihomo/update-geodata.sh
chmod 700 /opt/etc/mihomo/update-geodata.sh
/opt/etc/mihomo/update-geodata.sh
```

Скрипт выполняет следующие действия:

1. Определяет последний релиз и скачивает из него обе базы вместе с контрольными суммами.
2. Проверяет SHA-256 и запускает `mihomo -t` с новыми базами и сохранённым `config.yaml`.
3. Сравнивает скачанные файлы с установленными. Если содержимое совпадает, завершает работу без перезапуска.
4. Если базы изменились, сохраняет предыдущую пару, устанавливает новую и перезапускает XKeen.

При ошибке загрузки или проверки установленные базы сохраняются. При неудачном перезапуске скрипт восстанавливает предыдущую пару и пытается запустить её снова.

Для обновления вручную достаточно повторно выполнить:

```sh
/opt/etc/mihomo/update-geodata.sh
```

Изменения конфигурации применяются отдельно. Если базы уже установлены и были изменены только правила, проверьте конфиг и перезапустите XKeen:

```sh
xkeen -mtest && xkeen -restart
```

### Автоматическое обновление

Добавьте одну строку в существующий crontab роутера. Пример ниже запускает обновление ежедневно в 04:00 **по времени устройства**:

```cron
0 4 * * * PATH=/opt/sbin:/opt/bin:/usr/sbin:/usr/bin:/sbin:/bin /opt/etc/mihomo/update-geodata.sh >> /opt/var/log/update-geodata.log 2>&1
```

Каталог `/opt/var/log` должен существовать. Просмотреть последние сообщения можно командой:

```sh
tail -n 30 /opt/var/log/update-geodata.log
```

Для объединённых баз используйте один механизм обновления. Старые задания, которые записывают другие базы в `/opt/etc/mihomo/GeoSite.dat` или `/opt/etc/mihomo/GeoIP.dat`, нужно отключить.

Подписка на прокси-серверы обновляется независимо от геобаз. Её период задаётся в `proxy-providers.<имя>.interval`, а период проверки доступности узлов — в `health-check.interval`. Например, `3600` соответствует обновлению подписки раз в час, а `60` — проверке узлов раз в минуту. Для регулярных проверок без ожидания обращений к провайдеру используется `health-check.lazy: false`.

## Изменение списков и локальная сборка

Собственные записи хранятся в файлах:

- [geosite/data/all](geosite/data/all) — домены;
- [geoip/data/all.txt](geoip/data/all.txt) — IP-адреса и подсети.

После изменения списков отправьте изменения в `main` или `master`. GitHub Actions соберёт и опубликует обновлённые базы.

Для локальной сборки нужны Python 3.10 или новее, Go и Git. Дополнительные Python-пакеты не требуются. Выполните из корня репозитория:

```sh
python3 -m unittest discover -s tests -v
python3 tools/build.py
```

Скрипт загружает исходный код компиляторов V2Fly и внешние базы. Результаты сохраняются в `dist/`, служебные файлы — в `.cache/`. Ревизии компиляторов записываются в `manifest.json`. Для обновления компиляторов удалите `.cache/tools/` перед следующей сборкой.

Проверка всех категорий с установленным бинарным файлом Mihomo:

```sh
python3 tools/check_mihomo.py --binary /path/to/mihomo --dist dist
```

Для сборки с ранее загруженными внешними базами используйте:

```sh
python3 tools/build.py --upstream-dir /path/to/dat-files
```

В указанном каталоге должны находиться шесть файлов:

```text
v2fly-geosite.dat
v2fly-geoip.dat
refilter-geosite.dat
refilter-geoip.dat
zkeen-geosite.dat
zkeen-geoip.dat
```

Без `--upstream-dir` внешние базы загружаются заново при каждой сборке.

## Использование с Xray

Объединённые базы можно подключить через `ext:`, указав имя файла и категорию:

```json
{
  "domain": ["ext:GeoSite.dat:v2fly-youtube", "ext:GeoSite.dat:shvetsov-all"],
  "ip": ["ext:GeoIP.dat:shvetsov-all"]
}
```

Для существующих конфигураций также публикуются отдельные файлы `geosite_shvetsov.dat` и `geoip_shvetsov.dat`. В них собственные записи доступны под именем `all`, поэтому ссылки `ext:geosite_shvetsov.dat:all` и `ext:geoip_shvetsov.dat:all` остаются действительными.

Скрипт [router/update-rules.sh](router/update-rules.sh) обновляет эти отдельные файлы в `/opt/etc/xray/dat`. Для объединённых баз Mihomo используется [router/update-mihomo-geodata.sh](router/update-mihomo-geodata.sh).
