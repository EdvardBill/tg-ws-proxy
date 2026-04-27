#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

INIT_SCRIPT = "/opt/etc/init.d/S99tgwsproxy"
PID_FILE = "/var/run/tg-ws-proxy.pid"
SECRET_FILE = "/opt/home/admin/proxy_secret.txt"
PORT_FILE = "/opt/home/admin/proxy_port.txt"
HOST_FILE = "/opt/home/admin/proxy_host.txt"
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
            overflow: hidden;
            transition: background-color 0.3s ease;
        }
    
        .dark-mode-toggle {
            position: fixed;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: #111;
            border-radius: 50%;
            padding: 8px;
            cursor: pointer;
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
        }
    
        .dark-mode-toggle:hover {
            background: #222;
        }
    
        .dark-mode-toggle i {
            font-size: 16px;
            color: #fff;
        }
    
        .dark-mode-toggle.dark {
            background: #333;
        }
    
        .dark-mode-toggle.dark i {
            color: #fff;
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
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 32px;
        }
        .btn {
            flex: 1;
            min-width: 100px;
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            color: #e0e0e0;
            padding: 10px 8px;
            font-size: 13px;
            font-weight: 500;
            border-radius: 14px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }
        .btn i {
            font-size: 12px;
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
        .edit-icon {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 14px;
            padding: 4px 8px;
            border-radius: 8px;
            transition: all 0.2s;
            color: #28a745;
            flex-shrink: 0;
        }
        .edit-icon:active { transform: scale(0.9); color: #ffc107; background: rgba(255, 193, 7, 0.1); }
        .edit-input {
            flex: 1;
            font-family: 'SF Mono', 'Courier New', monospace;
            font-size: 12px;
            background: #080808;
            padding: 8px 12px;
            border-radius: 12px;
            border: 1px solid #28a745;
            color: #e0e0e0;
            outline: none;
        }
        .edit-input:focus { border-color: #ffc107; }
        .info-row .edit-input {
            font-family: 'SF Mono', 'Courier New', monospace;
            font-size: 12px;
            background: #080808;
            padding: 6px 10px;
            border-radius: 10px;
            border: 1px solid #1f1f1f;
            color: #e0e0e0;
            outline: none;
            min-width: 100px;
        }
        .info-row .edit-input:focus { border-color: #28a745; }
        .info-row input.edit-input {
            flex: 1;
            margin-right: 8px;
        }
        .settings-card {
            background: #0f0f0f;
            border: 1px solid #2a2a2a;
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .settings-card h3 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 16px;
            color: #ffc107;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .settings-card h3 i { font-size: 18px; }
        .settings-row {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
            padding: 12px 0;
            border-bottom: 1px solid #1f1f1f;
        }
        .settings-row:last-child { border-bottom: none; }
        .settings-label {
            font-weight: 500;
            min-width: 80px;
            font-size: 13px;
            color: #a0a0a0;
        }
        .btn-save {
            background: #28a745;
            border: 1px solid #28a745;
            color: #fff;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 14px;
            cursor: pointer;
            transition: all 0.2s;
            font-family: inherit;
            width: 100%;
            margin-top: 12px;
        }
        .btn-save:hover { background: #218838; }
        .btn-save:active { transform: scale(0.97); }
        .btn-save:disabled { background: #555; border-color: #555; cursor: not-allowed; }
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
            .btn { 
                padding: 8px 6px; 
                font-size: 12px;
                min-width: 80px;
            }
            .btn i { font-size: 11px; }
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
        
        /* Анимация пульсации для иконки */
        @keyframes pulseAnimation {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.15); }
        }
        
        .pulse-icon {
            display: inline-block;
            border-radius: 50%;
            animation: pulseAnimation 1s ease-in-out infinite;
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
            <input type="text" id="editHost" class="edit-input" onchange="checkChange()">
            <button class="copy-icon" onclick="copyValue('host')"><i class="fas fa-copy"></i></button>
        </div>
        <div class="info-row">
            <div class="info-label"><i class="fas fa-plug"></i> Порт</div>
            <input type="text" id="editPort" class="edit-input" onchange="checkChange()">
            <button class="copy-icon" onclick="copyValue('port')"><i class="fas fa-copy"></i></button>
        </div>
        <div class="info-row">
            <div class="info-label"><i class="fas fa-key"></i> Ключ</div>
            <input type="text" id="editSecret" class="edit-input" onchange="checkChange()">
            <button class="copy-icon" onclick="copyValue('secret')"><i class="fas fa-copy"></i></button>
        </div>
        <div class="info-row">
            <div class="info-label"><i class="fas fa-link"></i> Ссылка</div>
            <div id="link" class="info-link"></div>
        </div>
        <button id="btnRestart" class="btn-save" onclick="doRestart()" disabled><i class="fas fa-sync"></i> Перезапустить</button>
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
    let serverConfig = { host: '', port: '', secret: '' };
    let initialLoad = true;

    function showToast(msg) {
        let t = document.createElement('div');
        t.className = 'toast';
        t.textContent = msg;
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 2500);
    }
    function copyValue(type) {
        let el = document.getElementById('edit' + type.charAt(0).toUpperCase() + type.slice(1));
        let val = el.value.trim();
        if (type === 'secret') val = 'dd' + val;
        navigator.clipboard.writeText(val).then(() => showToast('✓')).catch(() => showToast('✗'));
    }
    function checkChange() {
        let h = document.getElementById('editHost').value.trim();
        let p = document.getElementById('editPort').value.trim();
        let s = document.getElementById('editSecret').value.trim();
        
        let changed = (h !== serverConfig.host) || (p !== serverConfig.port) || (s !== serverConfig.secret);
        document.getElementById('btnRestart').disabled = !changed;
    }
    function doRestart() {
        let h = document.getElementById('editHost').value.trim();
        let p = document.getElementById('editPort').value.trim();
        let s = document.getElementById('editSecret').value.trim();
        
        showToast('⟳ Сохранение...');
        
        Promise.all([
            fetch('/config?type=host&value=' + encodeURIComponent(h)).then(r => r.json()),
            fetch('/config?type=port&value=' + encodeURIComponent(p)).then(r => r.json()),
            fetch('/config?type=secret&value=' + encodeURIComponent(s)).then(r => r.json())
        ]).then(results => {
            let err = results.find(r => !r.ok);
            if (err && err.error) {
                showToast('✗ ' + err.error);
                return;
            }
            showToast('✓ Перезапуск...');
            serverConfig.host = h;
            serverConfig.port = p;
            serverConfig.secret = s;
            fetch('/restart', { method: 'POST' }).then(() => {
                setTimeout(updateStatus, 1500);
            }).catch(() => showToast('✗'));
        }).catch(() => showToast('✗'));
    }
    function sendAction(action) {
        fetch('/' + action, { method: 'POST' })
            .then(() => {
                showToast('⟳ ' + action + '...');
                setTimeout(updateStatus, 800);
            })
            .catch(() => showToast('✗'));
    }
    function renderLink() {
        let s = document.getElementById('editSecret').value.trim();
        let h = document.getElementById('editHost').value.trim();
        let p = document.getElementById('editPort').value.trim();
        let fs = 'dd' + s;
        let link = 'tg://proxy?server=' + h + '&port=' + p + '&secret=' + fs;
        document.getElementById('link').innerHTML = '<a href="' + link + '" target="_blank">' + link + '</a>';
    }
    function updateStatus() {
        fetch('/status?t=' + Date.now())
            .then(r => r.json())
            .then(d => {
                let sc = document.getElementById('statusCard');
                let ic = document.getElementById('infoCard');
                if (d.running) {
                    sc.className = 'status-card running';
                    sc.innerHTML = '<div class="status-icon"><i class="fas fa-circle pulse-icon" style="color:#28a745;"></i></div><div class="status-text">РАБОТАЕТ</div><div class="status-pid">PID: ' + d.pid + '</div>';
                    ic.style.display = 'block';
                    
                    // Только при первой загрузке обновляем значения с сервера
                    if (initialLoad) {
                        serverConfig.host = d.host || '';
                        serverConfig.port = d.port || '';
                        serverConfig.secret = d.secret || '';
                        document.getElementById('editHost').value = serverConfig.host;
                        document.getElementById('editPort').value = serverConfig.port;
                        document.getElementById('editSecret').value = serverConfig.secret;
                        initialLoad = false;
                    }
                    
                    renderLink();
                    checkChange();
                } else {
                    sc.className = 'status-card stopped';
                    sc.innerHTML = '<div class="status-icon"><i class="fas fa-circle" style="color:#ff3b30;"></i></div><div class="status-text">НЕ РАБОТАЕТ</div>';
                    ic.style.display = 'none';
                }
            })
            .catch(() => {
                let sc = document.getElementById('statusCard');
                sc.className = 'status-card stopped';
                sc.innerHTML = '<div class="status-icon"><i class="fas fa-exclamation-triangle"></i></div><div class="status-text">Ошибка</div>';
            });
    }
    document.getElementById('editHost').addEventListener('input', function() { checkChange(); renderLink(); });
    document.getElementById('editPort').addEventListener('input', function() { checkChange(); renderLink(); });
    document.getElementById('editSecret').addEventListener('input', function() { checkChange(); renderLink(); });
    setInterval(updateStatus, 10000);
    updateStatus();
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
                sec = ""
                port = "1443"
                host = ""
                if os.path.exists(SECRET_FILE):
                    with open(SECRET_FILE, encoding="utf-8", errors="ignore") as f:
                        sec = f.read().strip()
                if os.path.exists(PORT_FILE):
                    with open(PORT_FILE, encoding="utf-8", errors="ignore") as f:
                        port = f.read().strip() or "1443"
                if os.path.exists(HOST_FILE):
                    with open(HOST_FILE, encoding="utf-8", errors="ignore") as f:
                        host = f.read().strip()
                if not host:
                    host = get_lan_ip()
                self.wfile.write(
                    json.dumps(
                        {
                            "running": 1,
                            "pid": pid,
                            "host": host,
                            "port": port,
                            "secret": sec,
                        }
                    ).encode()
                )
            else:
                self.wfile.write(json.dumps({"running": 0}).encode())
            return
            
        if path.startswith("/config") or path.startswith("/save"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            qs = ""
            if "?" in path:
                qs = path.split("?", 1)[1]
            params = {}
            for pair in qs.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = urllib.parse.unquote(v)
            type_ = params.get("type", "")
            value = params.get("value", "")
            ok = False
            error = ""
            if type_ == "secret":
                if len(value) == 32 and all(c in "0123456789abcdef" for c in value.lower()):
                    try:
                        with open(SECRET_FILE, "w", encoding="utf-8") as f:
                            f.write(value.lower())
                        ok = True
                    except OSError as e:
                        error = str(e)
                else:
                    error = "Неверный формат (32 hex)"
            elif type_ == "port":
                try:
                    p = int(value)
                    if 1 <= p <= 65535:
                        with open(PORT_FILE, "w", encoding="utf-8") as f:
                            f.write(str(p))
                        ok = True
                    else:
                        error = "Порт 1-65535"
                except ValueError:
                    error = "Неверный порт"
            elif type_ == "host":
                import re
                if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", value):
                    with open(HOST_FILE, "w", encoding="utf-8") as f:
                        f.write(value)
                    ok = True
                else:
                    error = "Неверный IP"
            self.wfile.write(json.dumps({"ok": ok, "error": error}).encode())
            return
            
        if path in ("/start", "/stop", "/restart"):
            action = path.lstrip("/")
            run_init(action)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        self.do_GET()

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
