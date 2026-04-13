#!/bin/sh

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
MAGENTA="\033[1;35m"
CYAN="\033[1;36m"
RED="\033[1;31m"
BLUE="\033[0;34m"
NC="\033[0m"

REPO_URL="https://raw.githubusercontent.com/EdvardBill/tg-ws-proxy/main"

BIN_PATH="/opt/bin/tg-ws-proxy"
INIT_PATH="/opt/etc/init.d/S99tgwsproxy"
SECRET_FILE="/opt/home/admin/proxy_secret.txt"
INFO_FILE="/opt/home/admin/proxy_info.txt"
LOG_FILE="/var/log/tg-ws-proxy.log"
WEB_SERVER="/tmp/web.py"

PROXY_REPO_URL="https://github.com/Flowseal/tg-ws-proxy/archive/refs/heads/master.zip"

HOME_DIR="/opt/home/admin"
PROXY_DIR="$HOME_DIR/tg-ws-proxy"

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
    return 0
}

install_unzip() {
    if command -v unzip >/dev/null 2>&1; then
        echo -e "${GREEN}UnZip уже установлен .... [OK]${NC}"
    else
        opkg install unzip > /dev/null 2>&1
    fi
    return 0
}

install_wget() {
    if command -v wget >/dev/null 2>&1; then
        echo -e "${GREEN}Wget уже установлен .... [OK]${NC}"
    else
        opkg install wget > /dev/null 2>&1
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
    [ -z "$IP" ] && IP="192.168.1.1"
    echo "$IP"
}

stop_all_proxy() {
    echo -e "${CYAN}Останавливаем старые процессы...${NC}"
    killall python3 2>/dev/null
    if [ -f "$INIT_PATH" ]; then
        $INIT_PATH stop 2>/dev/null
    fi
    ps | grep "proxy.tg_ws_proxy" | grep -v grep | awk '{print $1}' | xargs kill -9 2>/dev/null
    sleep 2
}

download_init_script() {
    echo -e "${CYAN}Скачиваем init-скрипт из Git...${NC}"
    wget -q --no-check-certificate -O "$INIT_PATH" "$REPO_URL/init/S99tgwsproxy"
    if [ ! -f "$INIT_PATH" ]; then
        echo -e "${RED}Ошибка: не удалось скачать init-скрипт${NC}"
        return 1
    fi
    chmod +x "$INIT_PATH"
    echo -e "${GREEN}Init-скрипт загружен${NC}"
}

download_web_interface() {
    echo -e "${CYAN}Скачиваем веб-интерфейс из Git...${NC}"
    wget -q --no-check-certificate -O "$WEB_SERVER" "$REPO_URL/src/web.py"
    if [ ! -f "$WEB_SERVER" ]; then
        echo -e "${RED}Ошибка: не удалось скачать веб-интерфейс${NC}"
        return 1
    fi
    chmod +x "$WEB_SERVER"
    echo -e "${GREEN}Веб-интерфейс загружен${NC}"
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
    mkdir -p /opt/etc/init.d
    
    install_python || return 1
    install_unzip || return 1
    install_wget || return 1
    refresh_path
    
    echo -e "${CYAN}Скачиваем TG WS Proxy из репозитория Flowseal...${NC}"
    cd "$HOME_DIR" || return 1
    rm -rf "$PROXY_DIR"
    
    if ! wget --no-check-certificate -q --timeout=30 -O tg-ws-proxy.zip "$PROXY_REPO_URL" 2>/dev/null; then
        curl -k -L --connect-timeout 30 -s -o tg-ws-proxy.zip "$PROXY_REPO_URL"
    fi
    
    if [ ! -f "tg-ws-proxy.zip" ]; then
        echo -e "${RED}Ошибка скачивания!${NC}"
        PAUSE
        return 1
    fi
    
    echo -e "${CYAN}Распаковываем...${NC}"
    unzip -o tg-ws-proxy.zip > /dev/null 2>&1
    
    # Исправлено: сначала проверяем main, потом master
    if [ -d "tg-ws-proxy-main" ]; then
        mv tg-ws-proxy-main tg-ws-proxy
    elif [ -d "tg-ws-proxy-master" ]; then
        mv tg-ws-proxy-master tg-ws-proxy
    else
        echo -e "${RED}Ошибка: не найдена папка с прокси${NC}"
        PAUSE
        return 1
    fi
    
    rm -f tg-ws-proxy.zip
    
    cd "$PROXY_DIR" || return 1
    
    SECRET=$(generate_secret)
    echo "$SECRET" > "$SECRET_FILE"
    
    download_init_script || return 1
    download_web_interface || return 1
    
    echo -e "${CYAN}Запускаем сервисы...${NC}"
    $INIT_PATH start
    sleep 2
    python3 "$WEB_SERVER" &
    
    if ! grep -q "tg-ws-proxy" /etc/storage/started_script.sh 2>/dev/null; then
        cat >> /etc/storage/started_script.sh << 'EOF'

# TG WS Proxy
/opt/etc/init.d/S99tgwsproxy start
python3 /tmp/web.py &
EOF
        chmod +x /etc/storage/started_script.sh
        /sbin/mtd_storage.sh save
    fi
    
    sleep 2
    if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
        echo -e "\n${GREEN}════════════════════════════════════════${NC}"
        echo -e "${GREEN}        УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!${NC}"
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo -e "\n${CYAN}Веб-интерфейс:${NC} http://$(get_router_ip):8081"
        echo -e "${CYAN}Порт прокси:${NC} 1443"
        echo -e "${CYAN}Ключ:${NC} dd$SECRET"
        echo -e "\n${CYAN}Ссылка для Telegram:${NC} tg://proxy?server=$(get_router_ip)&port=1443&secret=dd$SECRET"
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
    
    echo -e "${CYAN}Останавливаем сервисы...${NC}"
    killall python3 2>/dev/null
    [ -f "$INIT_PATH" ] && $INIT_PATH stop 2>/dev/null
    ps | grep "proxy.tg_ws_proxy" | grep -v grep | awk '{print $1}' | xargs kill -9 2>/dev/null
    
    echo -e "${CYAN}Удаляем файлы...${NC}"
    rm -rf "$PROXY_DIR"
    rm -f "$BIN_PATH"
    rm -f "$INIT_PATH"
    rm -f "$SECRET_FILE"
    rm -f "$INFO_FILE"
    rm -f "$LOG_FILE"
    rm -f "$WEB_SERVER"
    
    echo -e "${CYAN}Удаляем из автозапуска...${NC}"
    sed -i '/TG WS Proxy/d' /etc/storage/started_script.sh 2>/dev/null
    sed -i '/S99tgwsproxy/d' /etc/storage/started_script.sh 2>/dev/null
    sed -i '/web.py/d' /etc/storage/started_script.sh 2>/dev/null
    
    /sbin/mtd_storage.sh save > /dev/null 2>&1
    
    echo -e "${CYAN}Удаляем скрипт...${NC}"
    rm -f "$0"
    
    echo -e "\n${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}        УДАЛЕНИЕ ЗАВЕРШЕНО!${NC}"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    exit 0
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
    clear
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         TG WS Proxy для Padavan        ║${NC}"
    echo -e "${BLUE}║                    by save55           ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    
    if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
        PID=$(pgrep -f "proxy.tg_ws_proxy" | head -1)
        LOCAL_IP=$(get_router_ip)
        SECRET=$(cat "$SECRET_FILE" 2>/dev/null)
        echo -e "\n${YELLOW}Статус: ${GREEN}● ЗАПУЩЕН${NC} (PID:${PID})"
        echo -e "\n${CYAN}  Веб-интерфейс:${NC} http://$LOCAL_IP:8081"
        echo -e "\n${CYAN}  Хост:${NC} $LOCAL_IP"
        echo -e "${CYAN}  Порт:${NC} 1443"
        echo -e "${CYAN}  Ключ:${NC} dd$SECRET"
        echo -e "\n${CYAN}  Ссылка:${NC} tg://proxy?server=$LOCAL_IP&port=1443&secret=dd$SECRET"
    else
        echo -e "\n${YELLOW}Статус: ${RED}○ НЕ ЗАПУЩЕН${NC}"
    fi
    
    echo -e "\n${GREEN}1) Установить${NC}"
    echo -e "${GREEN}2) Удалить${NC}"
    echo -e "${GREEN}3) Перезапустить${NC}"
    echo -e "${GREEN}0) Выход${NC}"
    echo -en "\n${YELLOW}Выберите пункт [0-3]: ${NC}"
    read choice
    
    case "$choice" in
        1) install_proxy ;;
        2) delete_proxy ;;
        3) restart_proxy ;;
        0) exit 0 ;;
        *) PAUSE ;;
    esac
}

while true; do
    menu
done
