# TG WS Proxy Manager for Padavan
**Локальный MTProto-прокси** для Telegram, который **ускоряет работу Telegram**, перенаправляя трафик через WebSocket-соединения. Данные передаются в том же зашифрованном виде, а для работы не нужны сторонние сервера.

## Как это работает
```
Telegram Desktop → MTProto Proxy (192.168.1.1:1443) → WebSocket → Telegram DC
```

1. Скрипт поднимает MTProto прокси на `192.168.1.1:1443`
2. Перехватывает подключения к IP-адресам Telegram
3. Извлекает DC ID из MTProto obfuscation init-пакета
4. Устанавливает WebSocket (TLS) соединение к соответствующему DC через домены Telegram
5. Если WS недоступен (302 redirect) — автоматически переключается на CfProxy / прямое TCP-соединение


<img width="355" height="447" alt="telegram" src="https://github.com/user-attachments/assets/5c52b339-b8b7-4def-bc85-aa352e71a569" />

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
- Автоматическое добавление в автозагрузку роутера
- Запустит сервис

<img width="642" height="386" alt="menu" src="https://github.com/user-attachments/assets/3e1985bf-d445-4fd3-adef-353c280964c4" />

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
