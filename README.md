radb-as-prefixes
Маленький CLI‑инструмент для получения IPv4/IPv6 префиксов по AS из RADb (через IRRd !g / !6) и вывода их в разных форматах: plain, JSON, nftables set, ipset script.

Не требует внешних утилит (whois, grep, sort и т.д.) — нужен только Python 3 со стандартной библиотекой (socket, ipaddress, argparse, json).

Возможности
Получение префиксов из RADb по origin‑AS через команды IRRd !gasN и !6asN.

Поддержка IPv4, IPv6 или обеих семейств.

Коллапс (агрегация) префиксов через ipaddress.collapse_addresses().

Поддержка форматов вывода:

plain — один CIDR на строку;

json — JSON‑массив строк;

nft-set — готовый сет для nftables;

ipset — shell‑скрипт для ipset.

Опциональное логирование в файл (--logs).

Установка
Требуется Python 3.
На OpenWrt установите пакеты:

bash
opkg install python3-base python3-codecs python3-idna python3-light
# или
opkg install python3
Использование
bash
./whois.py [AS] [options]
Если AS не указан, программа попросит ввести его вручную.

Примеры:

bash
# Оба семейства (по умолчанию)
./whois.py AS13335

# Ввод вручную
./whois.py
Enter AS (e.g. AS43515): AS13335
Управление семействами адресов
По умолчанию: IPv4 + IPv6.
Флаги:

bash
--ipv4     # Только IPv4
--ipv6     # Только IPv6
--ipv4 --ipv6  # То же, что по умолчанию (оба)
Примеры:

bash
./whois.py AS13335 --ipv4
./whois.py AS13335 --ipv6
Форматы вывода (--mode)
1. plain (по умолчанию)
bash
./whois.py AS13335
Результат — список CIDR‑блоков, по одному на строку.

2. json
bash
./whois.py AS13335 --mode json
Вывод:

json
["1.0.0.0/24", "1.1.1.0/24", "104.16.0.0/12", ...]
3. nft-set
Генерация готового файла с сетом для nftables:

bash
./whois.py AS13335 --mode nft-set --set-name cf_as13335 > /etc/nft/cf_as13335.nft
Пример содержимого:

text
set cf_as13335 {
    type ip_addr flags interval
    elements = { 1.0.0.0/24, 1.1.1.0/24, 2001:db8::/32 }
}
IPv4‑только:

bash
./whois.py AS13335 --ipv4 --mode nft-set --set-name cf_as13335_v4
IPv6‑только:

bash
./whois.py AS13335 --ipv6 --mode nft-set --set-name cf_as13335_v6
Использование в nftables:

text
table inet filter {
    include "/etc/nft/cf_as13335.nft"

    chain input {
        type filter hook input priority 0;
        ip saddr @cf_as13335 accept
        ip6 saddr @cf_as13335 accept
    }
}
4. ipset
Генерация shell‑скрипта для ipset:

bash
./whois.py AS13335 --ipv4 --mode ipset --set-name cf_as13335_v4 > cf_as13335_v4.sh
sh cf_as13335_v4.sh
Пример:

bash
ipset create cf_as13335_v4 hash:net family inet
ipset flush cf_as13335_v4
ipset add cf_as13335_v4 1.0.0.0/24
...
Важно: для --mode ipset нужно указать ровно одно семейство (--ipv4 или --ipv6), иначе будет ошибка.

Режим raw (--raw)
Вывод необъединённых (не коллапсированных) префиксов.

bash
# "сырой" текст
./whois.py AS13335 --raw

# JSON
./whois.py AS13335 --raw --mode json

# nftables для IPv4
./whois.py AS13335 --ipv4 --raw --mode nft-set --set-name cf_as13335_v4_raw
Логирование
Для записи отладочной информации:

bash
./whois.py AS13335 --ipv4 --logs radb.log > prefixes.txt
prefixes.txt — только CIDR‑ы (stdout)

radb.log — логи соединения, команды IRRd, счётчики и т.д.

Ошибка при невозможности открыть лог:

bash
./whois.py AS13335 --logs /root/radb.log
# stderr: cannot open log file ...
Обработка ошибок
Типичные ошибки и примеры:

Описание	Пример	Сообщение
Неверный формат AS	./whois.py 13335	AS number must be in the form AS12345
RADb недоступен	./whois.py AS13335	failed to connect to ...
Нет префиксов	./whois.py AS65535	No prefixes found for AS65535
Ошибочный вызов ipset	./whois.py AS13335 --mode ipset	must specify exactly one of --ipv4/--ipv6
Все ошибки пишутся в stderr, программа завершает работу с ненулевым кодом выхода.

