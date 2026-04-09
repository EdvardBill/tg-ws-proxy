# TG WS Proxy Manager for Padavan
**Локальный MTProto-прокси** для Telegram, который **ускоряет работу Telegram**, перенаправляя трафик через WebSocket-соединения. Данные передаются в том же зашифрованном виде, а для работы не нужны сторонние сервера.

## Как это работает
```
Telegram Desktop → MTProto Proxy (127.0.0.1:1443) → WebSocket → Telegram DC
```

1. Приложение поднимает MTProto прокси на `192.168.1.1:1443`
2. Перехватывает подключения к IP-адресам Telegram
3. Извлекает DC ID из MTProto obfuscation init-пакета
4. Устанавливает WebSocket (TLS) соединение к соответствующему DC через домены Telegram
5. Если WS недоступен (302 redirect) — автоматически переключается на CfProxy / прямое TCP-соединение

## Быстрая установка
```bash
# Скачиваем скрипт
wget -O /opt/bin/twpm.sh https://raw.githubusercontent.com/EdvardBill/tg-ws-proxy/main/twpm.sh

# Делаем исполняемым
chmod +x /opt/bin/twpm.sh

# Запускаем
/opt/bin/twpm.sh
```
- Скрипт автоматически установит Python
- Скачает и распакует прокси
- Сгенерирует секретный ключ
- Найдет свободный порт
- Запустит сервис

## Управление через консоль
```bash
# Запуск прокси
/opt/etc/init.d/S99tgwsproxy start

# Остановка прокси
/opt/etc/init.d/S99tgwsproxy stop

# Перезапуск прокси
/opt/etc/init.d/S99tgwsproxy restart

# Проверка статуса
pgrep -f "proxy.tg_ws_proxy"
```

Переменные окружения
```bash
BIN_PATH="/opt/bin/tg-ws-proxy"           # Исполняемый файл
INIT_PATH="/opt/etc/init.d/S99tgwsproxy"  # Init-скрипт
SECRET_FILE="/opt/home/admin/proxy_secret.txt"    # Секретный ключ
LOG_FILE="/var/log/tg-ws-proxy.log"      # Лог-файл
```
