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
<html>
<head>
<meta charset="utf-8">
<title>TG WS Proxy</title>
<style>
body{font-family:Arial;margin:20px;background:#f0f0f0}
.container{max-width:600px;margin:auto;background:white;padding:20px;border-radius:10px;text-align:center}
h2{color:#333;border-bottom:2px solid #28a745;padding-bottom:10px;margin-top:0}
button{padding:12px 24px;margin:5px;font-size:16px;cursor:pointer;border:none;border-radius:5px}
.start{background:#28a745;color:white}
.start:hover{background:#218838}
.stop{background:#dc3545;color:white}
.stop:hover{background:#c82333}
.restart{background:#ffc107;color:#333}
.restart:hover{background:#e0a800}
.status{padding:15px;margin:15px 0;border-radius:8px;text-align:center;font-weight:bold;font-size:16px}
.running{background:#d4edda;color:#155724;border:1px solid #c3e6cb}
.stopped{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb}
.info{background:#e9ecef;padding:15px;border-radius:8px;margin:15px 0;text-align:left}
.row{padding:8px 0;border-bottom:1px solid #dee2e6}
.label{font-weight:bold;display:inline-block;width:70px}
.value{font-family:monospace}
.instruction{background:#e8f4f8;padding:15px;border-radius:8px;margin:15px 0;text-align:left}
.footer{text-align:center;margin-top:20px;color:#6c757d;font-size:12px}
</style>
</head>
<body>
<div class="container">
<h2>TG WS Proxy</h2>
<div id="status" class="status stopped">Проверка статуса...</div>
<div>
<button class="start" onclick="location.href='/start'">ЗАПУСТИТЬ</button>
<button class="stop" onclick="location.href='/stop'">ОСТАНОВИТЬ</button>
<button class="restart" onclick="location.href='/restart'">ПЕРЕЗАПУСТИТЬ</button>
</div>
<div class="info">
<h3 style="margin-top:0">Данные для подключения</h3>
<div class="row"><span class="label">Хост:</span> <span id="host" class="value">-</span></div>
<div class="row"><span class="label">Порт:</span> <span id="port" class="value">-</span></div>
<div class="row"><span class="label">Ключ:</span> <span id="secret" class="value">-</span></div>
<div class="row"><span class="label">Ссылка:</span> <span id="link" class="value">-</span></div>
</div>
<div class="instruction">
<b>Инструкция для Telegram:</b><br>
1. Нажмите <b>ЗАПУСТИТЬ</b><br>
2. Настройки → Данные и память → Прокси<br>
3. Добавить прокси → тип <b>MTProto</b><br>
4. Хост, порт и ключ (с префиксом <b>dd</b>)
</div>
<div class="footer">
TG WS Proxy | WebSocket
</div>
</div>
<script>
function update(){
 fetch('/status')
   .then(r=>r.json())
   .then(d=>{
     var s=document.getElementById('status');
     if(d.running){
       s.className='status running';
       s.innerHTML='РАБОТАЕТ (PID: '+d.pid+')';
       document.getElementById('host').innerText=d.host;
       document.getElementById('port').innerText=d.port;
       document.getElementById('secret').innerText='dd'+d.secret;
       var link='tg://proxy?server='+d.host+'&port='+d.port+'&secret=dd'+d.secret;
       document.getElementById('link').innerHTML='<a href="'+link+'" target="_blank">'+link+'</a>';
     }else{
       s.className='status stopped';
       s.innerHTML='НЕ РАБОТАЕТ';
       document.getElementById('host').innerText='-';
       document.getElementById('port').innerText='-';
       document.getElementById('secret').innerText='-';
       document.getElementById('link').innerText='-';
     }
   });
}
setInterval(update,2000);
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
            # 302 надёжнее, чем HTML+script без Content-Type (кнопки в браузере «молчат»).
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
