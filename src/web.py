#!/usr/bin/env python3
import subprocess
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

HTML = '''<!DOCTYPE html>
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
<h2>📡 TG WS Proxy</h2>
<div id="status" class="status stopped">● Проверка статуса...</div>
<div>
<button class="start" onclick="location.href='/start'">▶ ЗАПУСТИТЬ</button>
<button class="stop" onclick="location.href='/stop'">■ ОСТАНОВИТЬ</button>
<button class="restart" onclick="location.href='/restart'">⟳ ПЕРЕЗАПУСТИТЬ</button>
</div>
<div class="info">
<h3 style="margin-top:0">📋 Данные для подключения</h3>
<div class="row"><span class="label">Хост:</span> <span id="host" class="value">-</span></div>
<div class="row"><span class="label">Порт:</span> <span id="port" class="value">-</span></div>
<div class="row"><span class="label">Ключ:</span> <span id="secret" class="value">-</span></div>
<div class="row"><span class="label">Ссылка:</span> <span id="link" class="value">-</span></div>
</div>
<div class="instruction">
<b>📖 Инструкция для Telegram:</b><br>
1. Нажмите кнопку <b>ЗАПУСТИТЬ</b><br>
2. Telegram: <b>Настройки → Данные и память → Прокси</b><br>
3. Нажмите <b>Добавить прокси</b> → Тип <b>MTProto</b><br>
4. Введите хост, порт и ключ (с <b>dd</b> в начале)
</div>
<div class="footer">
TG WS Proxy | Работает через WebSocket
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
       s.innerHTML='✅ РАБОТАЕТ (PID: '+d.pid+')';
       document.getElementById('host').innerText=d.host;
       document.getElementById('port').innerText=d.port;
       document.getElementById('secret').innerText='dd'+d.secret;
       var link='tg://proxy?server='+d.host+'&port='+d.port+'&secret=dd'+d.secret;
       document.getElementById('link').innerHTML='<a href=\"'+link+'\" target=\"_blank\">'+link+'</a>';
     }else{
       s.className='status stopped';
       s.innerHTML='❌ НЕ РАБОТАЕТ';
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
</html>'''

class H(BaseHTTPRequestHandler):
    def do_GET(s):
        s.send_response(200)
        if s.path == '/':
            s.send_header('Content-Type', 'text/html;charset=utf-8')
            s.end_headers()
            s.wfile.write(HTML.encode())
        elif s.path == '/status':
            s.send_header('Content-Type', 'application/json')
            s.end_headers()
            r = subprocess.run(['pgrep', '-f', 'proxy.tg_ws_proxy'], capture_output=True)
            if r.returncode == 0:
                pid = r.stdout.decode().split()[0]
                ip = subprocess.run(['nvram', 'get', 'lan_ipaddr'], capture_output=True, text=True).stdout.strip() or '192.168.1.1'
                sec = ''
                if os.path.exists('/opt/home/admin/proxy_secret.txt'):
                    with open('/opt/home/admin/proxy_secret.txt', 'r') as f:
                        sec = f.read().strip()
                s.wfile.write(json.dumps({'running': 1, 'pid': pid, 'host': ip, 'port': '1443', 'secret': sec}).encode())
            else:
                s.wfile.write(json.dumps({'running': 0}).encode())
        elif s.path in ('/start', '/stop', '/restart'):
            s.end_headers()
            subprocess.run(['/opt/etc/init.d/S99tgwsproxy', s.path[1:]])
            s.wfile.write(b'<script>location.href="/"</script>')
    def log_message(s, *a):
        pass

if __name__ == '__main__':
    print('Server: http://192.168.1.1:8081')
    HTTPServer(('0.0.0.0', 8081), H).serve_forever()
	