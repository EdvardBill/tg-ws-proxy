# TG WS Proxy Manager for Padavan
**Локальный MTProto-прокси** для Telegram, который **ускоряет работу Telegram**, перенаправляя трафик через WebSocket-соединения. Данные передаются в том же зашифрованном виде, а для работы не нужны сторонние сервера.

Быстрая установка
```bash
# Скачиваем скрипт
wget -O /opt/bin/twpm.sh https://raw.githubusercontent.com/EdvardBill/tg-ws-proxy/main/twpm.sh

# Делаем исполняемым
chmod +x /opt/bin/twpm.sh

# Запускаем
/opt/bin/twpm.sh
```
Скрипт автоматически установит Python
Скачает и распакует прокси
Сгенерирует секретный ключ
Найдет свободный порт
Запустит сервис

Управление через консоль
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
REPO_URL="https://github.com/Flowseal/tg-ws-proxy/archive/refs/heads/master.zip"
```
