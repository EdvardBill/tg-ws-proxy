#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

INIT_SCRIPT = "/opt/etc/init.d/S99tgwsproxy"
PID_FILE = "/var/run/tg-ws-proxy.pid"
SECRET_FILE = "/opt/home/admin/proxy_secret.txt"
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8081
PROXY_CMD_MARK = "proxy.tg_ws_proxy"


def get_lan_ip():
    try:
        r = subprocess.run(
            ["nvram", "get", "lan_ipaddr"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ip = (r.stdout or "").strip()
        if ip:
            return ip
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "192.168.1.1"


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def find_proxy_pid():
    """Status without pgrep (often missing on BusyBox routers)."""
    try:
        with open(PID_FILE, encoding="utf-8", errors="ignore") as f:
            pid = int(f.read().strip())
        if _pid_alive(pid):
            return str(pid)
    except (OSError, ValueError):
        pass

    try:
        r = subprocess.run(
            ["pgrep", "-f", PROXY_CMD_MARK],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    try:
        r = subprocess.run(["ps"], capture_output=True, text=True, timeout=5)
        for line in (r.stdout or "").splitlines():
            if PROXY_CMD_MARK not in line or "grep" in line:
                continue
            parts = line.split()
            for part in parts[:4]:
                if part.isdigit() and _pid_alive(int(part)):
                    return part
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
        pass

    return None


def run_init(action):
    subprocess.run(["sh", INIT_SCRIPT, action], check=False)


def _request_path(handler):
    raw = handler.path.split("?", 1)[0].split("#", 1)[0]
    raw = raw.strip() or "/"
    if raw != "/" and raw.endswith("/"):
        raw = raw.rstrip("/")
    return raw


HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#28a745">
<title>TG WS Proxy</title>
<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 16px;
    margin: 0;
}

.container {
    max-width: 500px;
    margin: 0 auto;
    background: white;
    border-radius: 24px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    overflow: hidden;
    animation: slideUp 0.4s ease-out;
}

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.header {
    background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
    padding: 24px 20px;
    text-align: center;
}

.header h1 {
    color: white;
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 8px;
}

.header p {
    color: rgba(255,255,255,0.9);
    font-size: 14px;
}

.content {
    padding: 24px 20px;
}

.status-card {
    background: #f8f9fa;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 24px;
    text-align: center;
    transition: all 0.3s ease;
}

.status-card.running {
    background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
    border: 1px solid #28a745;
}

.status-card.stopped {
    background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
    border: 1px solid #dc3545;
}

.status-icon {
    font-size: 48px;
    margin-bottom: 8px;
}

.status-text {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 4px;
}

.status-pid {
    font-size: 12px;
    opacity: 0.7;
    font-family: monospace;
}

.button-group {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
    flex-wrap: wrap;
}

.button-group button {
    flex: 1;
    min-width: 100px;
    padding: 14px 20px;
    font-size: 16px;
    font-weight: 600;
    border: none;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s ease;
    font-family: inherit;
    color: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.button-group button:active {
    transform: scale(0.97);
}

.btn-start {
    background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
}

.btn-stop {
    background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
}

.btn-restart {
    background: linear-gradient(135deg, #ffc107 0%, #ff9800 100%);
    color: #333;
}

.info-card {
    background: #f8f9fa;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 24px;
}

.info-card h3 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
    color: #333;
    display: flex;
    align-items: center;
    gap: 8px;
}

.info-row {
    display: flex;
    flex-wrap: wrap;
    padding: 12px 0;
    border-bottom: 1px solid #e0e0e0;
    align-items: center;
    gap: 8px;
}

.info-row:last-child {
    border-bottom: none;
}

.info-label {
    font-weight: 600;
    min-width: 60px;
    color: #666;
    font-size: 14px;
}

.info-value {
    flex: 1;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    word-break: break-all;
    color: #333;
    background: white;
    padding: 8px 12px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}

.info-value span {
    word-break: break-all;
    flex: 1;
}

.copy-icon {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 18px;
    padding: 4px 8px;
    border-radius: 6px;
    transition: all 0.2s;
    background: #e9ecef;
    flex-shrink: 0;
}

.copy-icon:active {
    transform: scale(0.9);
    background: #28a745;
    color: white;
}

.info-link {
    flex: 1;
}

.info-link a {
    color: #28a745;
    text-decoration: none;
    font-size: 13px;
    background: white;
    padding: 8px 12px;
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    word-break: break-all;
    width: 100%;
}

.instruction {
    background: #e8f4f8;
    border-radius: 16px;
    padding: 20px;
    border-left: 4px solid #28a745;
}

.instruction h3 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
    color: #333;
}

.instruction ol {
    padding-left: 20px;
}

.instruction li {
    margin: 8px 0;
    font-size: 13px;
    color: #555;
    line-height: 1.5;
}

.instruction b {
    color: #28a745;
}

.footer {
    text-align: center;
    padding: 20px;
    background: #f8f9fa;
    font-size: 11px;
    color: #999;
    border-top: 1px solid #e0e0e0;
}

@media (max-width: 480px) {
    body {
        padding: 8px;
    }
    
    .content {
        padding: 16px;
    }
    
    .button-group button {
        padding: 12px 16px;
        font-size: 14px;
    }
    
    .info-label {
        font-size: 12px;
        min-width: 50px;
    }
    
    .info-value {
        font-size: 11px;
        padding: 6px 10px;
    }
}

@media (max-width: 380px) {
    .button-group {
        flex-direction: column;
    }
    
    .button-group button {
        width: 100%;
    }
}

.loading {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid #f3f3f3;
    border-top: 2px solid #28a745;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-left: 8px;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.toast {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.8);
    color: white;
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 12px;
    z-index: 1000;
    animation: fadeOut 2s ease-out forwards;
}

@keyframes fadeOut {
    0% { opacity: 1; }
    70% { opacity: 1; }
    100% { opacity: 0; visibility: hidden; }
}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>TG WS Proxy</h1>
        <p>WebSocket MTProto Proxy</p>
    </div>
    
    <div class="content">
        <div id="statusCard" class="status-card stopped">
            <div class="status-icon">⏳</div>
            <div class="status-text">Загрузка...</div>
            <div class="status-pid"></div>
        </div>
        
        <div class="button-group">
            <button class="btn-start" onclick="sendAction('start')">Запустить</button>
            <button class="btn-stop" onclick="sendAction('stop')">Остановить</button>
            <button class="btn-restart" onclick="sendAction('restart')">Перезапустить</button>
        </div>
        
        <div id="infoCard" class="info-card" style="display:none;">
            <h3>📡 Данные для подключения</h3>
            <div class="info-row">
                <div class="info-label">🌐 Хост:</div>
                <div id="host" class="info-value"></div>
            </div>
            <div class="info-row">
                <div class="info-label">🔌 Порт:</div>
                <div id="port" class="info-value"></div>
            </div>
            <div class="info-row">
                <div class="info-label">🔑 Ключ:</div>
                <div id="secret" class="info-value"></div>
            </div>
            <div class="info-row">
                <div class="info-label">🔗 Ссылка:</div>
                <div id="link" class="info-link"></div>
            </div>
        </div>
        
        <div class="instruction">
            <h3>📖 Инструкция для Telegram</h3>
            <ol>
                <li>Нажмите <b>Запустить</b></li>
                <li>Настройки → Данные и память → Прокси</li>
                <li>Добавить прокси → тип <b>MTProto</b></li>
                <li>Введите хост, порт и ключ (с префиксом <b>dd</b>)</li>
                <li>Или просто нажмите на ссылку выше</li>
            </ol>
        </div>
    </div>
    
    <div class="footer">
        TG WS Proxy | WebSocket Proxy
    </div>
</div>

<script>
function showToast(message) {
    let toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('✅ Скопировано!');
    });
}

function sendAction(action) {
    fetch('/' + action)
        .then(() => {
            showToast('🔄 Выполняется ' + action + '...');
            setTimeout(update, 500);
        })
        .catch(() => {
            showToast('❌ Ошибка при выполнении');
        });
}

function update() {
    fetch('/status')
        .then(r => r.json())
        .then(d => {
            let statusCard = document.getElementById('statusCard');
            let infoCard = document.getElementById('infoCard');
            
            if (d.running) {
                statusCard.className = 'status-card running';
                statusCard.innerHTML = `
                    <div class="status-icon">✅</div>
                    <div class="status-text">РАБОТАЕТ</div>
                    <div class="status-pid">PID: ${d.pid}</div>
                `;
                
                infoCard.style.display = 'block';
                let fullSecret = 'dd' + d.secret;
                let link = 'tg://proxy?server=' + d.host + '&port=' + d.port + '&secret=' + fullSecret;
                
                document.getElementById('host').innerHTML = `
                    <span>${d.host}</span>
                    <button class="copy-icon" onclick="copyToClipboard('${d.host}')">📋</button>
                `;
                
                document.getElementById('port').innerHTML = `
                    <span>${d.port}</span>
                    <button class="copy-icon" onclick="copyToClipboard('${d.port}')">📋</button>
                `;
                
                document.getElementById('secret').innerHTML = `
                    <span>${fullSecret}</span>
                    <button class="copy-icon" onclick="copyToClipboard('${fullSecret}')">📋</button>
                `;
                
                document.getElementById('link').innerHTML = `
                    <a href="${link}" target="_blank">${link}</a>
                `;
            } else {
                statusCard.className = 'status-card stopped';
                statusCard.innerHTML = `
                    <div class="status-icon">❌</div>
                    <div class="status-text">НЕ РАБОТАЕТ</div>
                    <div class="status-pid"></div>
                `;
                infoCard.style.display = 'none';
            }
        })
        .catch(() => {
            let statusCard = document.getElementById('statusCard');
            statusCard.className = 'status-card stopped';
            statusCard.innerHTML = `
                <div class="status-icon">⚠️</div>
                <div class="status-text">Ошибка связи</div>
                <div class="status-pid"></div>
            `;
        });
}

setInterval(update, 3000);
update();
</script>
</body>
</html>"""


class ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        path = _request_path(self)

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html;charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode())
            return

        if path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            pid = find_proxy_pid()
            if pid:
                ip = get_lan_ip()
                sec = ""
                if os.path.exists(SECRET_FILE):
                    with open(SECRET_FILE, encoding="utf-8", errors="ignore") as f:
                        sec = f.read().strip()
                self.wfile.write(
                    json.dumps(
                        {
                            "running": 1,
                            "pid": pid,
                            "host": ip,
                            "port": "1443",
                            "secret": sec,
                        }
                    ).encode()
                )
            else:
                self.wfile.write(json.dumps({"running": 0}).encode())
            return

        if path in ("/start", "/stop", "/restart"):
            action = path.lstrip("/")
            run_init(action)
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    ip = get_lan_ip()
    print(f"Server: http://{ip}:{LISTEN_PORT}", flush=True)
    try:
        ReuseHTTPServer((LISTEN_HOST, LISTEN_PORT), H).serve_forever()
    except OSError as e:
        print(f"Bind error on port {LISTEN_PORT}: {e}", file=sys.stderr)
        sys.exit(1)
