#!/bin/sh

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
MAGENTA="\033[1;35m"
CYAN="\033[1;36m"
RED="\033[1;31m"
BLUE="\033[0;34m"
NC="\033[0m"

REPO_URL="https://raw.githubusercontent.com/EdvardBill/tg-ws-proxy/main"
PROXY_REPO_URL="https://github.com/Flowseal/tg-ws-proxy/archive/refs/heads/master.zip"

BIN_PATH="/opt/bin/tg-ws-proxy"
INIT_PATH="/opt/etc/init.d/S99tgwsproxy"
SECRET_FILE="/opt/home/admin/proxy_secret.txt"
INFO_FILE="/opt/home/admin/proxy_info.txt"
LOG_FILE="/var/log/tg-ws-proxy.log"
WEB_SERVER="/tmp/web.py"

if [ -d "/opt/home/admin" ]; then
    HOME_DIR="/opt/home/admin"
elif [ -d "/root" ]; then
    HOME_DIR="/root"
else
    HOME_DIR="/opt"
fi

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

refresh_path() {
    export PATH="/opt/bin:/opt/sbin:/opt/usr/bin:/usr/bin:/bin:/sbin:$PATH"
    hash -r 2>/dev/null
}

resolve_python_cmd() {
    if [ -f "/opt/bin/python3" ]; then
        echo "/opt/bin/python3"
    elif command -v python3 >/dev/null 2>&1; then
        echo "python3"
    else
        echo ""
    fi
}

have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

check_required_tools() {
    MISSING=""
    for cmd in sed awk grep xargs unzip wget; do
        if ! have_cmd "$cmd"; then
            MISSING="$MISSING $cmd"
        fi
    done
    if [ -n "$MISSING" ]; then
        echo -e "${RED}Ошибка: отсутствуют утилиты:$MISSING${NC}"
        echo -e "${YELLOW}Установите недостающие пакеты и повторите.${NC}"
        return 1
    fi
    return 0
}

check_optional_tools() {
    WARNED=0
    if ! have_cmd pgrep || ! have_cmd pkill; then
        echo -e "${YELLOW}Предупреждение: pgrep/pkill не найдены, будет использован fallback через ps/awk.${NC}"
        WARNED=1
    fi
    if ! have_cmd curl; then
        echo -e "${YELLOW}Предупреждение: curl не найден, резервная загрузка недоступна.${NC}"
        WARNED=1
    fi
    if ! have_cmd hexdump; then
        echo -e "${YELLOW}Предупреждение: hexdump не найден, генерация секрета перейдет на fallback.${NC}"
        WARNED=1
    fi
    if ! have_cmd md5sum && ! have_cmd sha256sum; then
        echo -e "${YELLOW}Предупреждение: md5sum/sha256sum не найдены, будет использован минимальный fallback секрета.${NC}"
        WARNED=1
    fi
    [ "$WARNED" -eq 1 ] && echo
    return 0
}

install_python() {
    echo -e "${MAGENTA}Проверяем наличие Python...${NC}"
    PYTHON_CMD=$(resolve_python_cmd)
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${YELLOW}Python не найден. Устанавливаем...${NC}"
        opkg update > /dev/null 2>&1
        opkg install python3 python3-pip python3-dev > /dev/null 2>&1
        refresh_path
        PYTHON_CMD=$(resolve_python_cmd)
    fi
    if [ -n "$PYTHON_CMD" ]; then
        if [ "$PYTHON_CMD" = "python3" ]; then
            echo -e "${GREEN}$(python3 --version 2>&1) найден .... [OK]${NC}"
        else
            echo -e "${GREEN}$($PYTHON_CMD --version 2>&1) найден .... [OK]${NC}"
        fi
    else
        echo -e "${RED}Ошибка: python3 не найден после установки.${NC}"
        return 1
    fi
    opkg install python3-cryptography > /dev/null 2>&1
    return 0
}

install_unzip() {
    if have_cmd unzip; then
        echo -e "${GREEN}UnZip уже установлен .... [OK]${NC}"
    else
        opkg install unzip > /dev/null 2>&1
    fi
    return 0
}

install_wget() {
    if have_cmd wget; then
        echo -e "${GREEN}Wget уже установлен .... [OK]${NC}"
    else
        opkg install wget > /dev/null 2>&1
    fi
    return 0
}

generate_secret() {
    SECRET=""
    if have_cmd hexdump; then
        SECRET=$(head -c16 /dev/urandom 2>/dev/null | hexdump -e '16/1 "%02x"' 2>/dev/null)
    elif have_cmd od; then
        SECRET=$(head -c16 /dev/urandom 2>/dev/null | od -An -tx1 2>/dev/null | tr -d ' \n')
    fi
    if [ -z "$SECRET" ]; then
        if have_cmd md5sum; then
            SECRET=$(date +%s | md5sum | cut -d' ' -f1)
        elif have_cmd sha256sum; then
            SECRET=$(date +%s | sha256sum | cut -c1-32)
        else
            SECRET="$(date +%s)$$"
        fi
    fi
    echo "$SECRET"
}

get_router_ip() {
    IP=$(nvram get lan_ipaddr 2>/dev/null)
    [ -z "$IP" ] && IP="192.168.1.1"
    echo "$IP"
}

stop_proxy_processes() {
    # Сначала мягко завершаем процесс прокси.
    if have_cmd pgrep && have_cmd pkill; then
        if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
            pkill -f "proxy.tg_ws_proxy" 2>/dev/null
            sleep 1
        fi
        # Если процесс не завершился, применяем принудительное завершение.
        if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
            pkill -9 -f "proxy.tg_ws_proxy" 2>/dev/null
        fi
        return 0
    fi

    # Fallback для систем без pgrep/pkill (например, урезанный BusyBox).
    PIDS=$(ps | awk '/proxy\.tg_ws_proxy/ && !/awk/ {print $1}')
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs kill 2>/dev/null
        sleep 1
    fi
    # Если процесс не завершился, применяем принудительное завершение.
    PIDS=$(ps | awk '/proxy\.tg_ws_proxy/ && !/awk/ {print $1}')
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs kill -9 2>/dev/null
    fi
}

stop_web_server_process() {
    if have_cmd pgrep; then
        pgrep -f "$WEB_SERVER" | xargs kill 2>/dev/null
        return 0
    fi
    PIDS=$(ps | awk -v ws="$WEB_SERVER" '$0 ~ ws && !/awk/ {print $1}')
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs kill 2>/dev/null
    fi
}

stop_all_proxy() {
    echo -e "${CYAN}Останавливаем старые процессы...${NC}"
    if [ -f "$INIT_PATH" ]; then
        $INIT_PATH stop 2>/dev/null
    fi
    # Останавливаем только веб-интерфейс текущего скрипта, не все python3 процессы.
    stop_web_server_process
    stop_proxy_processes
    sleep 2
}

download_web_interface() {
    echo -e "${CYAN}Скачиваем веб-интерфейс управления...${NC}"
    if ! wget -q -O "$WEB_SERVER" "$REPO_URL/src/web.py"; then
        rm -f "$WEB_SERVER"
        echo -e "${RED}Ошибка: не удалось скачать веб-интерфейс${NC}"
        return 1
    fi
    if [ ! -s "$WEB_SERVER" ]; then
        rm -f "$WEB_SERVER"
        echo -e "${RED}Ошибка: не удалось скачать веб-интерфейс${NC}"
        return 1
    fi
    chmod +x "$WEB_SERVER"
    echo -e "${GREEN}Веб-интерфейс загружен${NC}"
}

download_init_script() {
    echo -e "${CYAN}Скачиваем init-скрипт...${NC}"
    if ! wget -q -O "$INIT_PATH" "$REPO_URL/init/S99tgwsproxy"; then
        rm -f "$INIT_PATH"
        echo -e "${RED}Ошибка: не удалось скачать init-скрипт${NC}"
        return 1
    fi
    if [ ! -s "$INIT_PATH" ]; then
        rm -f "$INIT_PATH"
        echo -e "${RED}Ошибка: не удалось скачать init-скрипт${NC}"
        return 1
    fi
    chmod +x "$INIT_PATH"
    echo -e "${GREEN}Init-скрипт загружен${NC}"
}

install_proxy() {
    echo -e "${MAGENTA}     УСТАНОВКА TG WS PROXY${NC}"
    
    check_entware || return 1
    check_required_tools || return 1
    check_optional_tools
    stop_all_proxy
    
    mkdir -p "$(dirname "$SECRET_FILE")"
    mkdir -p "$(dirname "$INFO_FILE")"
    mkdir -p "$(dirname "$LOG_FILE")"
    
    install_python || return 1
    install_unzip || return 1
    install_wget || return 1
    refresh_path
    
    echo -e "${CYAN}Подготовка к установке...${NC}"
    rm -rf "$PROXY_DIR"
    rm -f "$BIN_PATH"
    
    echo -e "${CYAN}Скачиваем TG WS Proxy из репозитория...${NC}"
    cd "$HOME_DIR" || return 1
    if ! wget -q --timeout=30 -O tg-ws-proxy.zip "$PROXY_REPO_URL" 2>/dev/null; then
        if ! curl -L --connect-timeout 30 -s -o tg-ws-proxy.zip "$PROXY_REPO_URL"; then
            echo -e "${RED}Ошибка скачивания!${NC}"
            PAUSE
            return 1
        fi
    fi
    
    if [ ! -f "tg-ws-proxy.zip" ] || [ ! -s "tg-ws-proxy.zip" ]; then
        echo -e "${RED}Ошибка: файл не скачан или пустой${NC}"
        PAUSE
        return 1
    fi
    
    echo -e "${CYAN}Распаковываем...${NC}"
    unzip -o tg-ws-proxy.zip > /dev/null 2>&1
    
    if [ -d "tg-ws-proxy-master" ]; then
        mv tg-ws-proxy-master tg-ws-proxy
        PROXY_DIR="$HOME_DIR/tg-ws-proxy"
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
    fi
    
    SECRET=$(generate_secret)
    echo "$SECRET" > "$SECRET_FILE"
    
    download_init_script || return 1
    download_web_interface || return 1
    
    echo -e "${CYAN}Запускаем сервисы...${NC}"
    $INIT_PATH start
    sleep 2
    "$PYTHON_CMD" "$WEB_SERVER" &
    
    if ! grep -q "tg-ws-proxy" /etc/storage/started_script.sh 2>/dev/null; then
        cat >> /etc/storage/started_script.sh << 'EOF'

# TG WS Proxy
/opt/etc/init.d/S99tgwsproxy start
/opt/bin/python3 /tmp/web.py &
EOF
        chmod +x /etc/storage/started_script.sh 2>/dev/null
        /sbin/mtd_storage.sh save > /dev/null 2>&1
    fi
    
    sleep 3
    if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
        echo -e "${GREEN}        УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!${NC}"
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
    stop_web_server_process
    [ -f "$INIT_PATH" ] && $INIT_PATH stop 2>/dev/null
    stop_proxy_processes
    
    echo -e "${CYAN}Удаляем файлы...${NC}"
    rm -rf "$PROXY_DIR"
    rm -f "$BIN_PATH"
    rm -f "$INIT_PATH"
    rm -f "$SECRET_FILE"
    rm -f "$INFO_FILE"
    rm -f "$HOME_DIR/tg-ws-proxy.zip"
    rm -f "$LOG_FILE"
    rm -f "$WEB_SERVER"
    
    PYTHON_CMD=$(resolve_python_cmd)
    SITE_PACKAGES=""
    if [ -n "$PYTHON_CMD" ]; then
        SITE_PACKAGES=$($PYTHON_CMD -c "import site; print(site.getsitepackages()[0])" 2>/dev/null)
    fi
    if [ -n "$SITE_PACKAGES" ]; then
        rm -rf "$SITE_PACKAGES/proxy" 2>/dev/null
    fi
    
    echo -e "${CYAN}Удаляем из автозапуска...${NC}"
    sed -i '/TG WS Proxy/d' /etc/storage/started_script.sh 2>/dev/null
    sed -i '/S99tgwsproxy/d' /etc/storage/started_script.sh 2>/dev/null
    sed -i '\|/opt/bin/python3 /tmp/web.py &|d' /etc/storage/started_script.sh 2>/dev/null
    
    /sbin/mtd_storage.sh save > /dev/null 2>&1
    
    echo -e "${CYAN}Удаляем скрипт...${NC}"
    rm -f "$0"
    
    echo -e "${GREEN}        УДАЛЕНИЕ ЗАВЕРШЕНО!${NC}"
    echo -e "${YELLOW}Скрипт удален. Нажмите Enter для выхода...${NC}"
    read dummy
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
    refresh_path
    clear
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         TG WS Proxy для Padavan        ║${NC}"
    echo -e "${BLUE}║                       by save55        ║${NC}"
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
