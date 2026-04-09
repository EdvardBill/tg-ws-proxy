#!/bin/sh
# TG WS Proxy Manager for Padavan - установка, удаление и управление Telegram WebSocket прокси

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
MAGENTA="\033[1;35m"
CYAN="\033[1;36m"
RED="\033[1;31m"
BLUE="\033[0;34m"
NC="\033[0m"

BIN_PATH="/opt/bin/tg-ws-proxy"
INIT_PATH="/opt/etc/init.d/S99tgwsproxy"
SECRET_FILE="/opt/home/admin/proxy_secret.txt"
INFO_FILE="/opt/home/admin/proxy_info.txt"
LOG_FILE="/var/log/tg-ws-proxy.log"
REPO_URL="https://github.com/Flowseal/tg-ws-proxy/archive/refs/heads/master.zip"

if [ -d "/opt/home/admin" ]; then
    HOME_DIR="/opt/home/admin"
elif [ -d "/root" ]; then
    HOME_DIR="/root"
else
    HOME_DIR="/opt"
fi

PROXY_DIR="$HOME_DIR/tg-ws-proxy-flowseal"
export PATH="/opt/bin:/opt/sbin:/opt/usr/bin:/usr/bin:/bin:/sbin:$PATH"

PAUSE() {
    echo -ne "\n${YELLOW}Нажмите Enter...${NC}"
    read dummy
}

check_entware() {
    if [ ! -d "/opt/bin" ] || [ ! -f "/opt/etc/opkg.conf" ]; then
        echo -e "${RED}Ошибка: Entware не найден. Установите Entware сначала.${NC}"
        PAUSE
        return 1
    fi
    return 0
}

refresh_path() {
    export PATH="/opt/bin:/opt/sbin:/opt/usr/bin:/usr/bin:/bin:/sbin:$PATH"
    hash -r 2>/dev/null
}

install_python() {
    echo -e "${MAGENTA}Проверяем наличие Python...${NC}"
    if [ -f "/opt/bin/python3" ]; then
        PYTHON_CMD="/opt/bin/python3"
        echo -e "${GREEN}$($PYTHON_CMD --version 2>&1) найден .... [OK]${NC}"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
        echo -e "${GREEN}$(python3 --version 2>&1) найден .... [OK]${NC}"
    else
        echo -e "${YELLOW}Python не найден. Устанавливаем...${NC}"
        opkg update > /dev/null 2>&1
        opkg install python3 python3-pip python3-dev > /dev/null 2>&1
        refresh_path
        PYTHON_CMD="/opt/bin/python3"
    fi
    opkg install python3-cryptography > /dev/null 2>&1
    return 0
}

install_unzip() {
    if command -v unzip >/dev/null 2>&1; then
        echo -e "${GREEN}UnZip уже установлен .... [OK]${NC}"
    elif command -v busybox >/dev/null 2>&1 && busybox --list 2>/dev/null | grep -q "unzip"; then
        echo -e "${GREEN}BusyBox UnZip доступен...${NC}"
    else
        echo -e "${MAGENTA}Будем использовать Python для распаковки...${NC}"
    fi
    return 0
}

generate_secret() {
    SECRET=$(head -c16 /dev/urandom 2>/dev/null | hexdump -e '16/1 "%02x"' 2>/dev/null)
    if [ -z "$SECRET" ]; then
        SECRET=$(date +%s | md5sum | cut -d' ' -f1)
    fi
    echo "$SECRET"
}

get_router_ip() {
    IP=$(nvram get lan_ipaddr 2>/dev/null)
    [ -z "$IP" ] && IP=$(ifconfig br0 2>/dev/null | grep 'inet addr' | cut -d: -f2 | awk '{print $1}')
    [ -z "$IP" ] && IP=$(ifconfig eth2.2 2>/dev/null | grep 'inet addr' | cut -d: -f2 | awk '{print $1}')
    [ -z "$IP" ] && IP="192.168.1.1"
    echo "$IP"
}

find_free_port() {
    PORT=1443
    while netstat -tuln 2>/dev/null | grep -q ":$PORT "; do
        PORT=$((PORT + 1))
        [ $PORT -gt 1453 ] && PORT=8443
    done
    echo "$PORT"
}

stop_all_proxy() {
    echo -e "${CYAN}Останавливаем старые процессы...${NC}"
    killall tg-ws-proxy 2>/dev/null
    killall python3 2>/dev/null
    ps | grep "proxy.tg_ws_proxy" | grep -v grep | awk '{print $1}' | xargs kill -9 2>/dev/null
    [ -f "$INIT_PATH" ] && $INIT_PATH stop 2>/dev/null
    sleep 2
}

install_proxy() {
    echo -e "\n${MAGENTA}════════════════════════════════════════${NC}"
    echo -e "${MAGENTA}     УСТАНОВКА TG WS PROXY${NC}"
    echo -e "${MAGENTA}════════════════════════════════════════${NC}"
    check_entware || return 1
    stop_all_proxy
    mkdir -p "$(dirname "$SECRET_FILE")"
    mkdir -p "$(dirname "$INFO_FILE")"
    mkdir -p "$(dirname "$LOG_FILE")"
    install_python || return 1
    install_unzip || return 1
    refresh_path
    echo -e "${CYAN}Подготовка к установке...${NC}"
    rm -rf "$PROXY_DIR"
    rm -f "$BIN_PATH" "$INIT_PATH"
    echo -e "${CYAN}Скачиваем TG WS Proxy...${NC}"
    cd "$HOME_DIR" || return 1
    if ! /opt/bin/wget-ssl --no-check-certificate -q --timeout=30 -O tg-ws-proxy.zip "$REPO_URL" 2>/dev/null; then
        if ! wget --no-check-certificate -q --timeout=30 -O tg-ws-proxy.zip "$REPO_URL" 2>/dev/null; then
            if ! curl -k -L --connect-timeout 30 -s -o tg-ws-proxy.zip "$REPO_URL"; then
                echo -e "${RED}Ошибка скачивания!${NC}"
                echo -e "${YELLOW}Попробуйте скачать вручную:${NC}"
                echo "  cd $HOME_DIR"
                echo "  wget --no-check-certificate -O tg-ws-proxy.zip $REPO_URL"
                PAUSE
                return 1
            fi
        fi
    fi
    if [ ! -f "tg-ws-proxy.zip" ] || [ ! -s "tg-ws-proxy.zip" ]; then
        echo -e "${RED}Ошибка: файл не скачан или пустой${NC}"
        PAUSE
        return 1
    fi
    echo -e "${CYAN}Распаковываем...${NC}"
    $PYTHON_CMD -c "
import zipfile
try:
    with zipfile.ZipFile('tg-ws-proxy.zip', 'r') as zf:
        zf.extractall('.')
except Exception as e:
    print(e)
    exit(1)
" > /dev/null 2>&1
    if [ -d "tg-ws-proxy-master" ]; then
        mv tg-ws-proxy-master tg-ws-proxy-flowseal
    elif [ -d "tg-ws-proxy-main" ]; then
        mv tg-ws-proxy-main tg-ws-proxy-flowseal
    else
        echo -e "${RED}Ошибка: не найдена папка с прокси${NC}"
        PAUSE
        return 1
    fi
    rm -f tg-ws-proxy.zip
    cd "$PROXY_DIR" || return 1
    echo -e "${CYAN}Устанавливаем модуль...${NC}"
    SITE_PACKAGES=$($PYTHON_CMD -c "import site; print(site.getsitepackages()[0])" 2>/dev/null)
    if [ -n "$SITE_PACKAGES" ]; then
        cp -r proxy "$SITE_PACKAGES/"
        cp -r ui "$SITE_PACKAGES/" 2>/dev/null
        cp -r utils "$SITE_PACKAGES/" 2>/dev/null
    fi
    SECRET=$(generate_secret)
    PORT=$(find_free_port)
    echo "$SECRET" > "$SECRET_FILE"
    echo -e "${CYAN}Создаем скрипт запуска...${NC}"
    cat > "$BIN_PATH" << EOF
#!/bin/sh
export PATH="/opt/bin:\$PATH"
exec $PYTHON_CMD -m proxy.tg_ws_proxy --host 0.0.0.0 --port $PORT --secret $SECRET
EOF
    chmod +x "$BIN_PATH"
    cat > "$INIT_PATH" << EOF
#!/bin/sh
export PATH="/opt/bin:\$PATH"
PROG="$BIN_PATH"
start() {
    \$PROG > $LOG_FILE 2>&1 &
    echo \$! > /var/run/tg-ws-proxy.pid
}
stop() {
    pkill -f "proxy.tg_ws_proxy" 2>/dev/null
    rm -f /var/run/tg-ws-proxy.pid
}
case "\$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; sleep 2; start ;;
    *) exit 1 ;;
esac
EOF
    chmod +x "$INIT_PATH"
    echo -e "${CYAN}Запускаем сервис...${NC}"
    $INIT_PATH start
    sleep 3
    if [ ! -f "/etc/storage/started_script.sh" ] || ! grep -q "S99tgwsproxy" /etc/storage/started_script.sh 2>/dev/null; then
        echo "/opt/etc/init.d/S99tgwsproxy start" >> /etc/storage/started_script.sh
        chmod +x /etc/storage/started_script.sh 2>/dev/null
    fi
    if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
        echo -e "${GREEN}УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!${NC}"
    else
        echo -e "\n${RED}Ошибка: Сервис не запустился.${NC}"
        echo -e "${YELLOW}Проверьте логи: cat $LOG_FILE${NC}"
    fi
    PAUSE
}

delete_proxy() {
    echo -e "\n${MAGENTA}════════════════════════════════════════${NC}"
    echo -e "${MAGENTA}     УДАЛЕНИЕ TG WS PROXY${NC}"
    echo -e "${MAGENTA}════════════════════════════════════════${NC}"
    echo -e "${CYAN}Останавливаем сервис...${NC}"
    [ -f "$INIT_PATH" ] && $INIT_PATH stop 2>/dev/null
    killall tg-ws-proxy 2>/dev/null
    ps | grep "proxy.tg_ws_proxy" | grep -v grep | awk '{print $1}' | xargs kill -9 2>/dev/null
    echo -e "${CYAN}Удаляем файлы...${NC}"
    rm -rf "$PROXY_DIR"
    rm -f "$BIN_PATH"
    rm -f "$INIT_PATH"
    rm -f "$SECRET_FILE"
    rm -f "$INFO_FILE"
    rm -f "$HOME_DIR/tg-ws-proxy.zip"
    rm -f "$LOG_FILE"
    SITE_PACKAGES=$($PYTHON_CMD -c "import site; print(site.getsitepackages()[0])" 2>/dev/null)
    if [ -n "$SITE_PACKAGES" ]; then
        rm -rf "$SITE_PACKAGES/proxy" "$SITE_PACKAGES/ui" "$SITE_PACKAGES/utils" 2>/dev/null
    fi
    echo -e "${CYAN}Удаляем из автозапуска...${NC}"
    sed -i '/S99tgwsproxy/d' /etc/storage/started_script.sh 2>/dev/null
    echo -e "\n${GREEN}УДАЛЕНИЕ ЗАВЕРШЕНО!${NC}"
    PAUSE
}

restart_proxy() {
    if [ -f "$INIT_PATH" ]; then
        echo -e "\n${MAGENTA}Перезапускаем сервис...${NC}"
        $INIT_PATH restart
        sleep 3
        if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Сервис перезапущен${NC}"
        else
            echo -e "${RED}Ошибка при перезапуске${NC}"
        fi
    else
        echo -e "\n${RED}Прокси не установлен!${NC}"
    fi
    PAUSE
}

menu() {
    refresh_path
    clear
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         TG WS Proxy для Padavan        ║${NC}"
    echo -e "${BLUE}║                       by save55        ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
        PID=$(pgrep -f "proxy.tg_ws_proxy" | head -1)
        PORT=$(netstat -tuln 2>/dev/null | grep LISTEN | grep -E "1443|8443" | head -1 | awk '{print $4}' | cut -d: -f2)
        LOCAL_IP=$(get_router_ip)
        SECRET=$(cat "$SECRET_FILE" 2>/dev/null)
        echo -e "\n${YELLOW}Статус: ${GREEN}● ЗАПУЩЕН${NC} (PID:${PID})"
        echo -e "\n${CYAN}  Хост:${NC} $LOCAL_IP"
        echo -e "${CYAN}  Порт:${NC} ${PORT:-1443}"
        echo -e "${CYAN}  Ключ:${NC} dd$SECRET"
        echo -e "\n${CYAN}  Ссылка:${NC} tg://proxy?server=$LOCAL_IP&port=${PORT:-1443}&secret=dd$SECRET"
    else
        echo -e "\n${YELLOW}Статус: ${RED}○ НЕ ЗАПУЩЕН${NC}"
    fi
    echo -e "\n${GREEN}1) Установить прокси${NC}"
    echo -e "${GREEN}2) Удалить прокси${NC}"
    echo -e "${GREEN}3) Перезапустить сервис${NC}"
    echo -e "${GREEN}0) Выход${NC}"
    echo -en "\n${YELLOW}Выберите пункт [0-3]: ${NC}"
    read choice
    case "$choice" in
        1) install_proxy ;;
        2) delete_proxy ;;
        3) restart_proxy ;;
        0)
            clear
            echo -e "${GREEN}До свидания!${NC}"
            exit 0
            ;;
        *)
            echo -e "\n${RED}Неверный выбор!${NC}"
            PAUSE
            ;;
    esac
}

while true; do
    menu
done