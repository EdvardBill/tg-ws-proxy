#!/bin/sh
# TG WS Proxy Manager for Padavan

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
MAGENTA="\033[1;35m"
CYAN="\033[1;36m"
RED="\033[1;31m"
BLUE="\033[0;34m"
NC="\033[0m"

REPO_URL="https://raw.githubusercontent.com/EdvardBill/tg-ws-proxy/main"
PROXY_REPO_URL="https://github.com/Flowseal/tg-ws-proxy/archive/refs/heads/main.zip"
PROXY_REPO_URL_ALT="https://github.com/Flowseal/tg-ws-proxy/archive/refs/heads/master.zip"

BIN_PATH="/opt/bin/tg-ws-proxy"
INIT_PATH="/opt/etc/init.d/S99tgwsproxy"
SECRET_FILE="/opt/home/admin/proxy_secret.txt"
PID_FILE="/var/run/tg-ws-proxy.pid"
INFO_FILE="/opt/home/admin/proxy_info.txt"
LOG_FILE="/var/log/tg-ws-proxy.log"
WEB_SERVER="/tmp/web.py"
WEB_LOG="/tmp/tg-ws-web.log"

run_init() {
    [ -f "$INIT_PATH" ] || return 1
    sh "$INIT_PATH" "$@"
}

strip_cr_file() {
    f="$1"
    [ -f "$f" ] || return 1
    tmp="${f}.tmp.$$"
    if ! tr -d '\r' < "$f" > "$tmp" 2>/dev/null; then
        rm -f "$tmp"
        return 1
    fi
    mv "$tmp" "$f"
}

patch_init_if_no_pkill() {
    [ -f "$INIT_PATH" ] || return 0
    if have_cmd pkill; then
        return 0
    fi
    sed -i '/pkill.*proxy\.tg_ws_proxy/d' "$INIT_PATH" 2>/dev/null || true
}

proxy_process_running() {
    if have_cmd pgrep; then
        pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1
        return $?
    fi
    ps | grep "proxy.tg_ws_proxy" | grep -v grep > /dev/null 2>&1
    return $?
}

proxy_process_pid() {
    if have_cmd pgrep; then
        pgrep -f "proxy.tg_ws_proxy" | head -1
        return
    fi
    ps | grep "proxy.tg_ws_proxy" | grep -v grep | awk '{print $1}' | head -1
}

monitor_system() {
    CPU_USAGE="N/A"
    MEM_USAGE="N/A"
    
    # Memory usage
    if have_cmd free; then
        MEM_RAW=$(free 2>/dev/null | grep Mem | awk '{print int($3/$2 * 100)}')
        [ -n "$MEM_RAW" ] && MEM_USAGE="$MEM_RAW"
    fi
    
    echo -e "${CYAN}Система: MEM ${MEM_USAGE}%${NC}"
}

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
        echo -e "${RED}Ошибка: Entware не найден. Попытка автоматической установки...${NC}"
        if ! command -v opkg >/dev/null 2>&1; then
            ARCH=$(uname -m)
            if [ "$ARCH" = "mipsel" ] || [ "$ARCH" = "mips" ]; then
                echo -e "${CYAN}Детектирована архитектура $ARCH. Скачиваем Entware...${NC}"
                mkdir -p /opt
                cd /opt
                if [ -f "entware-install.sh" ]; then
                    rm -f entware-install.sh
                fi
                curl -s -O https://bin.entware.net/mipssf-k3.4/entware-install.sh
                chmod +x entware-install.sh
                ./entware-install.sh
                if [ $? -ne 0 ]; then
                    echo -e "${RED}Ошибка: Не удалось установить Entware автоматически. Установите вручную.${NC}"
                    PAUSE
                    exit 1
                fi
            else
                echo -e "${RED}Ошибка: Неподдерживаемая архитектура $ARCH. Установите Entware вручную.${NC}"
                PAUSE
                exit 1
            fi
        fi
        if [ ! -d "/opt/bin" ] || [ ! -f "/opt/etc/opkg.conf" ]; then
            echo -e "${RED}Ошибка: Entware всё ещё не установлен. Установите вручную.${NC}"
            PAUSE
            exit 1
        fi
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
    if command -v "$1" >/dev/null 2>&1; then
        return 0
    fi
    for d in /opt/bin /opt/sbin /opt/usr/bin /usr/bin /bin /sbin /usr/sbin; do
        if [ -x "$d/$1" ]; then
            return 0
        fi
    done
    return 1
}

busybox_path() {
    for bb in busybox /bin/busybox /usr/bin/busybox /sbin/busybox; do
        if [ -x "$bb" ]; then
            echo "$bb"
            return 0
        fi
        if command -v "$bb" >/dev/null 2>&1; then
            command -v "$bb"
            return 0
        fi
    done
    for p in /bin/sed /bin/grep /bin/awk /usr/bin/sed /usr/bin/grep; do
        [ -e "$p" ] || continue
        tgt=$(readlink "$p" 2>/dev/null)
        [ -n "$tgt" ] || continue
        case "$tgt" in
            /*)
                if [ -x "$tgt" ]; then
                    echo "$tgt"
                    return 0
                fi
                ;;
            busybox)
                dir=$(dirname "$p")
                if [ -x "$dir/busybox" ]; then
                    echo "$dir/busybox"
                    return 0
                fi
                ;;
            */busybox)
                dir=$(dirname "$p")
                if [ -x "$dir/$tgt" ]; then
                    echo "$dir/$tgt"
                    return 0
                fi
                ;;
        esac
    done
    return 1
}

have_tool() {
    if have_cmd "$1"; then
        return 0
    fi
    BB=$(busybox_path) || return 1
    case "$1" in
        sed)   echo ok | "$BB" sed 's/ok/ok/' >/dev/null 2>&1 ;;
        awk)   echo ok | "$BB" awk '{print $1}' >/dev/null 2>&1 ;;
        grep)  echo ok | "$BB" grep ok >/dev/null 2>&1 ;;
        xargs) echo ok | "$BB" xargs echo >/dev/null 2>&1 ;;
        *)     "$BB" "$1" --help >/dev/null 2>&1 ;;
    esac
}

check_required_tools() {
    MISSING=""
    for cmd in sed awk grep xargs; do
        if ! have_tool "$cmd"; then
            MISSING="$MISSING $cmd"
        fi
    done
    if [ -n "$MISSING" ]; then
        echo -e "${YELLOW}Не удалось найти утилиты:$MISSING${NC}"
        echo -e "${CYAN}Пробуем установить через opkg (Entware)...${NC}"
        opkg update >/dev/null 2>&1
        opkg install sed grep gawk findutils >/dev/null 2>&1 || true
        refresh_path
        MISSING=""
        for cmd in sed awk grep xargs; do
            if ! have_tool "$cmd"; then
                MISSING="$MISSING $cmd"
            fi
        done
    fi
    if [ -n "$MISSING" ]; then
        echo -e "${RED}Ошибка: отсутствуют утилиты:$MISSING${NC}"
        echo -e "${YELLOW}Установите вручную: opkg update && opkg install sed grep gawk findutils${NC}"
        return 1
    fi
    return 0
}

check_optional_tools() {
    return 0
}

install_python() {
    PYTHON_CMD=$(resolve_python_cmd)
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${YELLOW}Python не найден. Устанавливаем...${NC}"
        opkg update > /dev/null 2>&1
        ARCH=$(uname -m)
        if [ "$ARCH" = "mipsel" ] || [ "$ARCH" = "mips" ]; then
            echo -e "${CYAN}Оптимизация для mipsel: устанавливаем python3-lite...${NC}"
            opkg install python3-lite python3-pip > /dev/null 2>&1
        else
            opkg install python3 python3-pip python3-dev > /dev/null 2>&1
        fi
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
    if have_tool unzip; then
        echo -e "${GREEN}UnZip уже установлен .... [OK]${NC}"
    else
        opkg install unzip > /dev/null 2>&1
    fi
    return 0
}

install_wget() {
    if have_tool wget; then
        echo -e "${GREEN}Wget уже установлен .... [OK]${NC}"
    else
        opkg install wget > /dev/null 2>&1
    fi
    return 0
}

generate_secret() {
    SECRET=""
    if have_tool hexdump; then
        SECRET=$(head -c16 /dev/urandom 2>/dev/null | hexdump -e '16/1 "%02x"' 2>/dev/null)
    elif have_tool od; then
        SECRET=$(head -c16 /dev/urandom 2>/dev/null | od -An -tx1 2>/dev/null | tr -d ' \n')
    fi
    if [ -z "$SECRET" ]; then
        if have_tool md5sum; then
            SECRET=$(date +%s | md5sum | cut -d' ' -f1)
        elif have_tool sha256sum; then
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
    if have_cmd pgrep && have_cmd pkill; then
        if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
            pkill -f "proxy.tg_ws_proxy" 2>/dev/null
            sleep 1
        fi
        if pgrep -f "proxy.tg_ws_proxy" > /dev/null 2>&1; then
            pkill -9 -f "proxy.tg_ws_proxy" 2>/dev/null
        fi
        return 0
    fi
    PIDS=$(ps | awk '/proxy\.tg_ws_proxy/ && !/awk/ {print $1}')
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs kill 2>/dev/null
        sleep 1
    fi
    PIDS=$(ps | awk '/proxy\.tg_ws_proxy/ && !/awk/ {print $1}')
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs kill -9 2>/dev/null
    fi
}

stop_web_server_process() {
    n=0
    while [ "$n" -lt 4 ]; do
        n=$((n + 1))
        if have_cmd pgrep; then
            for pat in '/tmp/web.py' 'web.py'; do
                pids=$(pgrep -f "$pat" 2>/dev/null)
                for pid in $pids; do
                    kill "$pid" 2>/dev/null
                done
            done
        fi
        for pid in $(ps 2>/dev/null | awk '/\/tmp\/web\.py/ {print $1}'); do
            kill "$pid" 2>/dev/null
        done
        for pid in $(ps 2>/dev/null | awk '/python/ && /web\.py/ {print $1}'); do
            kill "$pid" 2>/dev/null
        done
        still=$(ps 2>/dev/null | awk '/\/tmp\/web\.py/ {print $1}')
        [ -z "$still" ] && break
        sleep 1
    done
    for pid in $(ps 2>/dev/null | awk '/\/tmp\/web\.py/ {print $1}'); do
        kill -9 "$pid" 2>/dev/null
    done
    if have_cmd fuser; then
        fuser -k 8081/tcp 2>/dev/null
    fi
}

stop_all_proxy() {
    echo -e "${CYAN}Останавливаем старые процессы...${NC}"
    if [ -f "$INIT_PATH" ]; then
        run_init stop 2>/dev/null
    fi
    stop_web_server_process
    stop_proxy_processes
    sleep 2
}

download_web_interface() {
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
    strip_cr_file "$WEB_SERVER"
    chmod +x "$WEB_SERVER"
    return 0
}

download_init_script() {
    mkdir -p "$(dirname "$INIT_PATH")" || true
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
    strip_cr_file "$INIT_PATH"
    patch_init_if_no_pkill
    chmod +x "$INIT_PATH"
    return 0
}

install_proxy() {
    echo -e "${MAGENTA}УСТАНОВКА TG WS PROXY${NC}"
    check_entware || return 1
    refresh_path
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
            if ! wget -q --timeout=30 -O tg-ws-proxy.zip "$PROXY_REPO_URL_ALT" 2>/dev/null; then
                if ! curl -L --connect-timeout 30 -s -o tg-ws-proxy.zip "$PROXY_REPO_URL_ALT"; then
                    echo -e "${RED}Ошибка скачивания!${NC}"
                    PAUSE
                    return 1
                fi
            fi
        fi
    fi
    if [ ! -f "tg-ws-proxy.zip" ] || [ ! -s "tg-ws-proxy.zip" ]; then
        echo -e "${RED}Ошибка: файл не скачан или пустой${NC}"
        PAUSE
        return 1
    fi
    echo -e "${CYAN}Распаковываем...${NC}"
    if ! unzip -o tg-ws-proxy.zip > /dev/null 2>&1; then
        echo -e "${RED}Ошибка: unzip не смог распаковать архив (файл битый или не zip).${NC}"
        PAUSE
        return 1
    fi
    SRC_DIR=""
    for d in tg-ws-proxy-main tg-ws-proxy-master; do
        if [ -d "$d" ]; then
            SRC_DIR="$d"
            break
        fi
    done
    if [ -z "$SRC_DIR" ]; then
        for d in tg-ws-proxy-*; do
            [ -d "$d" ] || continue
            SRC_DIR="$d"
            break
        done
    fi
    if [ -z "$SRC_DIR" ]; then
        for d in *; do
            [ -d "$d" ] || continue
            [ -d "$d/proxy" ] || continue
            SRC_DIR="$d"
            break
        done
    fi
    if [ -z "$SRC_DIR" ] || [ ! -d "$SRC_DIR/proxy" ]; then
        echo -e "${RED}Ошибка: не найдена папка с прокси (ожидается каталог с подпапкой proxy).${NC}"
        echo -e "${YELLOW}Содержимое $HOME_DIR после распаковки:${NC}"
        ls -la 2>/dev/null
        PAUSE
        return 1
    fi
    rm -rf tg-ws-proxy
    mv "$SRC_DIR" tg-ws-proxy
    PROXY_DIR="$HOME_DIR/tg-ws-proxy"
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
    if ! run_init start; then
        echo -e "${RED}Ошибка запуска init-скрипта. Попробуйте вручную: sh $INIT_PATH start${NC}"
    fi
    sleep 2
    stop_web_server_process
    sleep 1
    "$PYTHON_CMD" "$WEB_SERVER" >>"$WEB_LOG" 2>&1 &
    if ! grep -q "tg-ws-proxy" /etc/storage/started_script.sh 2>/dev/null; then
        cat >> /etc/storage/started_script.sh << 'EOF'

# TG WS Proxy
sh /opt/etc/init.d/S99tgwsproxy start
/opt/bin/python3 /tmp/web.py >>/tmp/tg-ws-web.log 2>&1 &
EOF
        chmod +x /etc/storage/started_script.sh 2>/dev/null
        /sbin/mtd_storage.sh save > /dev/null 2>&1
    fi
    sleep 3
       if proxy_process_running; then
        echo -e "${GREEN}УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!${NC}"
    else
        echo -e "\n${RED}Ошибка: Сервис не запустился.${NC}"
        echo -e "${YELLOW}Проверьте логи: cat $LOG_FILE${NC}"
    fi
    PAUSE
}

delete_proxy() {
    echo -e "${MAGENTA}УДАЛЕНИЕ TG WS PROXY${NC}"
    echo -e "${CYAN}Останавливаем сервисы...${NC}"
    stop_web_server_process
    [ -f "$INIT_PATH" ] && run_init stop 2>/dev/null
    stop_proxy_processes
    echo -e "${CYAN}Удаляем файлы...${NC}"
    rm -rf "$PROXY_DIR"
    rm -f "$BIN_PATH"
    rm -f "$INIT_PATH"
    rm -f "$SECRET_FILE"
    rm -f "$PID_FILE"
    rm -f "$INFO_FILE"
    rm -f "$HOME_DIR/tg-ws-proxy.zip"
    rm -f "$LOG_FILE"
    rm -f "$WEB_LOG"
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
    sed -i '\|sh /opt/etc/init.d/S99tgwsproxy|d' /etc/storage/started_script.sh 2>/dev/null
    sed -i '\|/opt/bin/python3 /tmp/web.py|d' /etc/storage/started_script.sh 2>/dev/null
    /sbin/mtd_storage.sh save > /dev/null 2>&1
    echo -e "${GREEN}УДАЛЕНИЕ ЗАВЕРШЕНО!${NC}"
    PAUSE
}

restart_proxy() {
    if [ -f "$INIT_PATH" ]; then
        echo -e "\n${MAGENTA}Перезапускаем сервис...${NC}"
        run_init restart
        sleep 3
        if proxy_process_running; then
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
   echo -e "${RED} ___________  _      ______  ___                   ${NC}"
    echo -e "${RED}/_  __/ ___/ | | /| / / __/ / _ \_______ __ ____ __${NC}"
    echo -e "${RED} / / / (_ /  | |/ |/ /\ \  / ___/ __/ _ \\\\ \ / // /${NC}"
    echo -e "${RED}/_/  \___/   |__/|__/___/ /_/  /_/  \___/_\_\\_, / ${NC}"
    echo -e "${RED}                                            /___/  ${NC}"
    if proxy_process_running; then
        PID=$(proxy_process_pid)
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
    monitor_system
    echo -e "\n${GREEN}1) Установить${NC}"
    echo -e "${GREEN}2) Удалить${NC}"
    echo -e "${GREEN}3) Перезапустить${NC}"
    echo -e "${GREEN}0) Выход${NC}"
    echo -en "\n${YELLOW}Выберите пункт [0-3]: ${NC}"
    read choice
    case "$choice" in
        1) install_proxy || PAUSE ;;
        2) delete_proxy || PAUSE ;;
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
