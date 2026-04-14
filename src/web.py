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
    <meta name="theme-color" content="#ff3b30">
    <title>TG WS Proxy для Padavan</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background-color: #050505;
            color: #e0e0e0;
            padding: 20px 16px 40px;
            margin: 0;
            min-height: 100vh;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 32px;
        }
        .header h1 {
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #ff3b30 0%, #ff6b6b 100%);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            letter-spacing: -0.5px;
        }
        .header p {
            font-size: 13px;
            color: #6c6c6c;
            margin-top: 6px;
        }
        .status-card {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 20px;
            padding: 24px 20px;
            text-align: center;
            margin-bottom: 24px;
            transition: all 0.2s ease;
        }
        .status-card.running {
            border-color: #28a745;
            box-shadow: 0 0 10px rgba(40, 167, 69, 0.2);
        }
        .status-card.stopped {
            border-color: #ff3b30;
            box-shadow: 0 0 8px rgba(255, 59, 48, 0.15);
        }
        .status-icon {
            font-size: 48px;
            margin-bottom: 12px;
        }
        .status-text {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .status-card.running .status-text {
            color: #28a745;
        }
        .status-card.stopped .status-text {
            color: #ff3b30;
        }
        .status-pid {
            font-size: 11px;
            font-family: monospace;
            color: #6c6c6c;
        }
        .button-group {
            display: flex;
            gap: 12px;
            margin-bottom: 32px;
        }
        .btn {
            flex: 1;
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            color: #e0e0e0;
            padding: 12px 16px;
            font-size: 15px;
            font-weight: 500;
            border-radius: 14px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .btn i {
            font-size: 14px;
        }
        .btn-start {
            border-color: #28a745;
            color: #28a745;
        }
        .btn-start:active { background: rgba(40, 167, 69, 0.1); transform: scale(0.97); }

        .btn-stop {
            border-color: #ff3b30;
            color: #ff3b30;
        }
        .btn-stop:active { background: rgba(255, 59, 48, 0.1); transform: scale(0.97); }

        .btn-restart {
            border-color: #ffc107;
            color: #ffc107;
        }
        .btn-restart:active { background: rgba(255, 193, 7, 0.1); transform: scale(0.97); }

        .info-card {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .info-card h3 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 16px;
            color: #ff3b30;
            display: flex;
            align-items: center;
            gap: 8px;
            letter-spacing: -0.3px;
        }
        .info-card h3 i {
            font-size: 18px;
        }
        .info-row {
            display: flex;
            flex-wrap: wrap;
            align-items: flex-start;
            gap: 12px;
            padding: 12px 0;
            border-bottom: 1px solid #1f1f1f;
        }
        .info-row:last-child { border-bottom: none; }
        .info-label {
            font-weight: 500;
            min-width: 55px;
            font-size: 13px;
            color: #a0a0a0;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .info-label i {
            font-size: 12px;
            width: 16px;
        }
        .info-value {
            flex: 1;
            font-family: 'SF Mono', 'Courier New', monospace;
            font-size: 12px;
            background: #080808;
            padding: 8px 12px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            word-break: break-all;
            border: 1px solid #1f1f1f;
        }
        .info-value span { flex: 1; }
        .copy-icon {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 14px;
            padding: 4px 8px;
            border-radius: 8px;
            transition: all 0.2s;
            color: #a0a0a0;
            flex-shrink: 0;
        }
        .copy-icon:active { transform: scale(0.9); color: #ff3b30; background: rgba(255, 59, 48, 0.1); }
        .info-link {
            flex: 1;
        }
        .info-link a {
            color: #28a745;
            text-decoration: none;
            font-size: 12px;
            font-family: monospace;
            background: #080808;
            padding: 8px 12px;
            border-radius: 12px;
            display: block;
            word-break: break-all;
            border: 1px solid #1f1f1f;
            transition: all 0.2s;
        }
        .info-link a:active { background: #1a1a1a; }
        .instruction {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .instruction h3 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 12px;
            color: #ff3b30;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .instruction ol {
            padding-left: 20px;
        }
        .instruction li {
            margin: 8px 0;
            font-size: 13px;
            color: #b0b0b0;
            line-height: 1.5;
        }
        .instruction b {
            color: #ff3b30;
        }
        .footer {
            text-align: center;
            font-size: 10px;
            color: #4a4a4a;
            margin-top: 20px;
            border-top: 1px solid #1a1a1a;
            padding-top: 20px;
        }
        .footer .version {
            color: #ff3b30;
            font-weight: 500;
        }
        @media (max-width: 480px) {
            body { padding: 16px 12px 32px; }
            .button-group { gap: 8px; }
            .btn { padding: 10px 12px; font-size: 14px; }
            .info-value { font-size: 11px; padding: 6px 10px; }
        }
        .toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #1f1f1f;
            border: 1px solid #ff3b30;
            color: #ff3b30;
            padding: 8px 20px;
            border-radius: 40px;
            font-size: 13px;
            font-weight: 500;
            z-index: 1000;
            animation: fadeOut 2s ease-out forwards;
            white-space: nowrap;
            backdrop-filter: blur(10px);
        }
        @keyframes fadeOut {
            0% { opacity: 1; transform: translateX(-50%) scale(1); }
            70% { opacity: 1; transform: translateX(-50%) scale(1); }
            100% { opacity: 0; transform: translateX(-50%) scale(0.95); visibility: hidden; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>TG WS Proxy</h1>
        <p>WebSocket MTProto Proxy для Padavan</p>
    </div>
    <div id="statusCard" class="status-card stopped">
        <div class="status-icon"><i class="fas fa-circle-notch fa-spin"></i></div>
        <div class="status-text">Загрузка...</div>
        <div class="status-pid"></div>
    </div>
    <div class="button-group">
        <button class="btn btn-start" onclick="sendAction('start')"><i class="fas fa-play"></i> Запустить</button>
        <button class="btn btn-stop" onclick="sendAction('stop')"><i class="fas fa-stop"></i> Остановить</button>
        <button class="btn btn-restart" onclick="sendAction('restart')"><i class="fas fa-sync-alt"></i> Перезапуск</button>
    </div>
    <div id="infoCard" class="info-card" style="display: none;">
        <h3><i class="fas fa-satellite-dish"></i> Данные для подключения</h3>
        <div class="info-row">
            <div class="info-label"><i class="fas fa-globe"></i> Хост</div>
            <div id="host" class="info-value"></div>
        </div>
        <div class="info-row">
            <div class="info-label"><i class="fas fa-plug"></i> Порт</div>
            <div id="port" class="info-value"></div>
        </div>
        <div class="info-row">
            <div class="info-label"><i class="fas fa-key"></i> Ключ</div>
            <div id="secret" class="info-value"></div>
        </div>
        <div class="info-row">
            <div class="info-label"><i class="fas fa-link"></i> Ссылка</div>
            <div id="link" class="info-link"></div>
        </div>
    </div>
    <div class="instruction">
        <h3><i class="fas fa-book-open"></i> Инструкция</h3>
        <ol>
            <li>Нажмите <b>Запустить</b></li>
            <li>Telegram: Настройки → Данные и память → Прокси</li>
            <li>Тип: <b>MTProto</b>, введите хост, порт и ключ (с <b>dd</b>)</li>
            <li>Или просто нажмите на ссылку выше</li>
        </ol>
    </div>
    <div class="footer">
        TG WS Proxy для Padavan | WebSocket MTProto Proxy<br>
        <span class="version">by save55</span>
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
            showToast('✓ Скопировано');
        }).catch(() => showToast('✗ Ошибка'));
    }
    function sendAction(action) {
        fetch('/' + action)
            .then(() => {
                showToast('⟳ ' + action + '...');
                setTimeout(update, 600);
            })
            .catch(() => showToast('✗ Ошибка связи'));
    }
    function update() {
        fetch('/status?t=' + Date.now())
            .then(r => r.json())
            .then(d => {
                const statusCard = document.getElementById('statusCard');
                const infoCard = document.getElementById('infoCard');

                if (d.running) {
                    statusCard.className = 'status-card running';
                    statusCard.innerHTML = `
                        <div class="status-icon"><i class="fas fa-circle" style="color: #28a745;"></i></div>
                        <div class="status-text">РАБОТАЕТ</div>
                        <div class="status-pid">PID: ${d.pid}</div>
                    `;
                    infoCard.style.display = 'block';
                    const fullSecret = 'dd' + d.secret;
                    const link = `tg://proxy?server=${d.host}&port=${d.port}&secret=${fullSecret}`;
                    document.getElementById('host').innerHTML = `<span>${d.host}</span><button class="copy-icon" onclick="copyToClipboard('${d.host}')"><i class="fas fa-copy"></i></button>`;
                    document.getElementById('port').innerHTML = `<span>${d.port}</span><button class="copy-icon" onclick="copyToClipboard('${d.port}')"><i class="fas fa-copy"></i></button>`;
                    document.getElementById('secret').innerHTML = `<span>${fullSecret}</span><button class="copy-icon" onclick="copyToClipboard('${fullSecret}')"><i class="fas fa-copy"></i></button>`;
                    document.getElementById('link').innerHTML = `<a href="${link}" target="_blank">${link}</a>`;
                } else {
                    statusCard.className = 'status-card stopped';
                    statusCard.innerHTML = `
                        <div class="status-icon"><i class="fas fa-circle" style="color: #ff3b30;"></i></div>
                        <div class="status-text">НЕ РАБОТАЕТ</div>
                        <div class="status-pid"></div>
                    `;
                    infoCard.style.display = 'none';
                }
            })
            .catch(() => {
                const statusCard = document.getElementById('statusCard');
                statusCard.className = 'status-card stopped';
                statusCard.innerHTML = `
                    <div class="status-icon"><i class="fas fa-exclamation-triangle"></i></div>
                    <div class="status-text">Ошибка</div>
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
